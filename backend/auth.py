import os
import secrets
import json
import base64
import hashlib
import logging
import ssl
from urllib.parse import urlencode
import certifi
import httpx
import jwt
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from .core import APP_URL, PRODUCTION, db, one, digest, demo_enabled, read_json

router=APIRouter(prefix='/api/auth')
logger=logging.getLogger(__name__)
# Python installations on macOS may not have a default CA bundle configured.
# Use the same trusted CA bundle as HTTPX for Google's signing-key download.
keys=jwt.PyJWKClient('https://www.googleapis.com/oauth2/v3/certs',cache_keys=True,timeout=10,
    ssl_context=ssl.create_default_context(cafile=certifi.where()))

def session_response(mid, redirect=False):
    token=secrets.token_hex(32)
    with db() as conn:
        conn.execute("INSERT INTO sessions(token_hash,member_id,expires_at) VALUES(%s,%s,now()+interval '7 days')",(digest(token),mid))
    response=RedirectResponse(APP_URL+'/discover',status_code=303) if redirect else JSONResponse({'ok':True})
    response.set_cookie('neighbor_session',token,httponly=True,samesite='lax',secure=PRODUCTION,max_age=604800,path='/')
    return response

@router.post('/demo')
async def demo(request: Request):
    if not demo_enabled():
        raise HTTPException(404,'Demo sign-in is disabled.')
    body=await read_json(request)
    m=one("SELECT id FROM members WHERE email=%s AND demo=true AND status='approved'",(body.get('email'),))
    if not m:
        raise HTTPException(404,'Demo account not found. Run the seed command.')
    return session_response(m['id'])

@router.post('/logout')
def logout(request: Request):
    token=request.cookies.get('neighbor_session')
    if token:
        with db() as conn:
            conn.execute('DELETE FROM sessions WHERE token_hash=%s',(digest(token),))
    response=JSONResponse({'ok':True})
    applicant_token=request.cookies.get('neighbor_applicant')
    if applicant_token:
        with db() as conn: conn.execute('DELETE FROM applicant_sessions WHERE token_hash=%s',(digest(applicant_token),))
    response.delete_cookie('neighbor_applicant',path='/')
    response.delete_cookie('neighbor_session',path='/')
    return response

@router.get('/google')
def google():
    if not os.getenv('GOOGLE_CLIENT_ID') or not os.getenv('GOOGLE_CLIENT_SECRET'):
        return RedirectResponse(APP_URL+'/?'+urlencode({'error':'Google sign-in is not configured. See the setup guide or use a local demo account.'}))
    state,nonce,verifier=secrets.token_urlsafe(32),secrets.token_urlsafe(32),secrets.token_urlsafe(32)
    # Store state server-side in a short-lived, signed JWT; no client-controlled OAuth values.
    secret=os.environ.get('SESSION_SECRET') or os.environ.get('INTAKE_SECRET','')
    if len(secret)<32:
        raise HTTPException(503,'Configure INTAKE_SECRET before using Google sign-in.')
    import time
    pending=jwt.encode({'state':state,'nonce':nonce,'verifier':verifier,'exp':int(time.time())+600},secret,algorithm='HS256')
    params={'client_id':os.environ['GOOGLE_CLIENT_ID'],'redirect_uri':APP_URL+'/api/auth/callback',
        'response_type':'code','scope':'openid email','prompt':'select_account','state':state,'nonce':nonce,
        'code_challenge':base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('='),'code_challenge_method':'S256'}
    response=RedirectResponse('https://accounts.google.com/o/oauth2/v2/auth?'+urlencode(params))
    response.set_cookie('neighbor_oauth',pending,httponly=True,samesite='lax',secure=PRODUCTION,max_age=600,path='/')
    return response

@router.get('/callback')
def callback(request: Request):
    stage='login_cookie'
    error_code='expired'
    try:
        if not request.cookies.get('neighbor_oauth'):
            raise ValueError('Your sign-in cookie is missing. Open '+APP_URL+' and start Google sign-in again from that address.')
        pending=jwt.decode(request.cookies.get('neighbor_oauth',''),(os.getenv('SESSION_SECRET') or os.getenv('INTAKE_SECRET','')),algorithms=['HS256'])
        if not secrets.compare_digest(request.query_params.get('state',''),pending['state']) or not request.query_params.get('code'):
            raise ValueError('Sign-in was cancelled or could not be verified.')
        stage='google_token'
        res=httpx.post('https://oauth2.googleapis.com/token',data={'code':request.query_params['code'],
            'client_id':os.environ['GOOGLE_CLIENT_ID'],'client_secret':os.environ['GOOGLE_CLIENT_SECRET'],
            'redirect_uri':APP_URL+'/api/auth/callback','grant_type':'authorization_code','code_verifier':pending['verifier']},timeout=10)
        res.raise_for_status()
        token=res.json()['id_token']
        stage='google_verification'
        payload=jwt.decode(token,keys.get_signing_key_from_jwt(token).key,algorithms=['RS256'],
            audience=os.environ['GOOGLE_CLIENT_ID'],issuer=['accounts.google.com','https://accounts.google.com'],
            options={'require':['exp','iat','sub','email','email_verified','nonce']})
        if payload['nonce']!=pending['nonce'] or payload['email_verified'] is not True:
            raise ValueError('Google account verification failed.')
        stage='member_lookup'
        with db() as conn:
            m=conn.execute("SELECT id,google_sub,status FROM members WHERE email=%s AND demo=false FOR UPDATE",(payload['email'].lower(),)).fetchone()
            if not m or m['status']=='pending':
                pending_form=conn.execute("SELECT 1 FROM submissions WHERE email=%s AND status='pending'",(payload['email'].lower(),)).fetchone()
                error_code='pending' if pending_form or m else 'wrong_account'
                raise ValueError('Your profile needs approval. Use the Google email you submitted on the form.')
            if m['status']!='approved':
                error_code='suspended' if m['status']=='suspended' else 'wrong_account'
                raise ValueError('This membership is suspended. Contact the community host.' if error_code=='suspended' else 'No active membership for this account.')
            if m['google_sub'] and m['google_sub']!=payload['sub']:
                error_code='wrong_account'
                raise ValueError('This profile is linked to a different Google account.')
            conn.execute('UPDATE members SET google_sub=%s WHERE id=%s',(payload['sub'],m['id']))
        stage='session_creation'
        response=session_response(m['id'],True)
    except ValueError as e:
        response=RedirectResponse(APP_URL+'/?'+urlencode({'error':str(e),'status':error_code}),status_code=303)
    except Exception as e:
        # Never log exception text, cookies, callback URLs, or Google tokens.
        logger.warning('Google sign-in failed: stage=%s exception=%s',stage,type(e).__name__)
        messages={
            'login_cookie':'Your sign-in session expired or could not be verified. Start Google sign-in again.',
            'google_token':'Could not complete the sign-in exchange with Google. Check the backend terminal for the failure type.',
            'google_verification':'Could not verify your Google sign-in. Check the backend terminal for the failure type.',
            'member_lookup':'Could not check your membership in the database. Check the backend terminal for the failure type.',
            'session_creation':'Could not save your login session. Check the backend terminal for the failure type.',
        }
        response=RedirectResponse(APP_URL+'/?'+urlencode({'error':'Sign-in is temporarily unavailable. Please try again shortly.','status':'temporary'}),status_code=303)
    response.delete_cookie('neighbor_oauth',path='/')
    return response
