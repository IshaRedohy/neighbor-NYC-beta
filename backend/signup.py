"""Optional Cognito managed login; no passwords or email codes handled by this app."""
import os
import time
import secrets
import hashlib
import base64
import ssl
from urllib.parse import urlencode
from uuid import uuid4
from typing import Literal
from pydantic import field_validator
import certifi
import httpx
import jwt
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from psycopg.types.json import Jsonb
from .core import APP_URL, PRODUCTION, db, one, member, digest, rate_limit
from .models import ProfileInput, Submission
from .intake import validate_zip
from .auth import session_response, logger

router = APIRouter(prefix='/api')


def enabled():
    return os.getenv('NATIVE_SIGNUP') == 'true'


def settings():
    if not enabled():
        raise HTTPException(404, 'Native signup is not enabled.')
    values = {k: os.getenv(k, '') for k in ('COGNITO_ISSUER', 'COGNITO_DOMAIN', 'COGNITO_CLIENT_ID', 'SESSION_SECRET')}
    if not all(values.values()) or len(values['SESSION_SECRET']) < 32:
        raise HTTPException(503, 'Sign-in is temporarily unavailable.')
    return values


def applicant(request):
    settings()
    token = request.cookies.get('neighbor_applicant', '')
    row = one('''SELECT i.* FROM applicant_sessions s JOIN login_identities i ON i.id=s.identity_id
        WHERE s.token_hash=%s AND s.expires_at>now()''', (digest(token),))
    if not row:
        raise HTTPException(401, 'Verify your email or Google account to continue.')
    return row


def start(request, link=False):
    cfg = settings()
    state, nonce, verifier = (secrets.token_urlsafe(32) for _ in range(3))
    pending = {'state': state, 'nonce': nonce, 'verifier': verifier, 'exp': int(time.time())+600}
    if link:
        me = member(request)
        pending.update({'member': str(me['id']), 'session': digest(request.cookies['neighbor_session'])})
    with db() as conn:
        conn.execute("INSERT INTO oauth_attempts(state_hash,expires_at) VALUES(%s,now()+interval '10 minutes')", (digest(state),))
    response = RedirectResponse(cfg['COGNITO_DOMAIN']+'/oauth2/authorize?'+urlencode({
        'client_id': cfg['COGNITO_CLIENT_ID'], 'redirect_uri': APP_URL+'/api/auth/cognito/callback',
        'response_type': 'code', 'scope': 'openid email', 'state': state, 'nonce': nonce,
        'code_challenge_method': 'S256',
        'code_challenge': base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('='),
        'prompt': 'login'}), status_code=303)
    response.set_cookie('neighbor_cognito', jwt.encode(pending, cfg['SESSION_SECRET'], algorithm='HS256'),
                        max_age=600, httponly=True, secure=PRODUCTION, samesite='lax', path='/')
    return response


@router.get('/auth/cognito')
def login(request: Request):
    return start(request)


@router.post('/auth/cognito/link')
def link(request: Request):
    # CSRF middleware + existing authenticated session + fresh managed authentication.
    return start(request, link=True)


@router.get('/auth/cognito/callback')
def callback(request: Request):
    cfg = settings()
    try:
        pending = jwt.decode(request.cookies.get('neighbor_cognito',''), cfg['SESSION_SECRET'], algorithms=['HS256'],
                             options={'require':['exp','state','nonce','verifier']})
        state = request.query_params.get('state','')
        if not secrets.compare_digest(state, pending['state']) or not request.query_params.get('code'):
            raise ValueError('state')
        with db() as conn:
            consumed = conn.execute('DELETE FROM oauth_attempts WHERE state_hash=%s AND expires_at>now() RETURNING state_hash',
                                     (digest(state),)).fetchone()
        if not consumed:
            raise ValueError('reused or expired flow')
        res = httpx.post(cfg['COGNITO_DOMAIN']+'/oauth2/token', data={
            'grant_type':'authorization_code','code':request.query_params['code'],
            'client_id':cfg['COGNITO_CLIENT_ID'],'redirect_uri':APP_URL+'/api/auth/cognito/callback',
            'code_verifier':pending['verifier']}, timeout=15)
        res.raise_for_status()
        token = res.json()['id_token']
        keys = jwt.PyJWKClient(cfg['COGNITO_ISSUER']+'/.well-known/jwks.json', timeout=10,
                               ssl_context=ssl.create_default_context(cafile=certifi.where()))
        payload = jwt.decode(token, keys.get_signing_key_from_jwt(token).key, algorithms=['RS256'],
            audience=cfg['COGNITO_CLIENT_ID'], issuer=cfg['COGNITO_ISSUER'],
            options={'require':['exp','iat','sub','email','email_verified','nonce','token_use']})
        if payload['nonce'] != pending['nonce'] or payload['email_verified'] is not True or payload['token_use'] != 'id':
            raise ValueError('unverified identity')
        email = payload['email'].lower()
        # Linking requires both identities to have been authenticated. Never merge by email alone.
        linking = member(request) if pending.get('member') else None
        if linking and (str(linking['id']) != pending['member'] or
                        digest(request.cookies.get('neighbor_session','')) != pending['session']):
            raise ValueError('link session changed')
        with db() as conn:
            conn.execute('SELECT pg_advisory_xact_lock(hashtext(%s))', (email,))
            identity = conn.execute('''INSERT INTO login_identities(issuer,subject,email) VALUES(%s,%s,%s)
                ON CONFLICT(issuer,subject) DO UPDATE SET email=EXCLUDED.email RETURNING *''',
                (cfg['COGNITO_ISSUER'], payload['sub'], email)).fetchone()
            if linking:
                existing = conn.execute('SELECT id FROM members WHERE email=%s', (email,)).fetchone()
                if (identity['member_id'] and identity['member_id'] != linking['id']) or (existing and existing['id'] != linking['id']):
                    raise ValueError('already linked')
                conn.execute('UPDATE login_identities SET member_id=%s WHERE id=%s', (linking['id'], identity['id']))
                identity['member_id'] = linking['id']
            m = conn.execute('SELECT status FROM members WHERE id=%s', (identity['member_id'],)).fetchone() if identity['member_id'] else None
        if m and m['status'] == 'approved':
            response = session_response(identity['member_id'], True)
            response.delete_cookie('neighbor_applicant', path='/')
        elif m and m['status'] in ('suspended','deleted'):
            response = RedirectResponse(APP_URL+'/?status=suspended', status_code=303)
        else:
            token = secrets.token_hex(32)
            with db() as conn:
                conn.execute("INSERT INTO applicant_sessions(token_hash,identity_id,expires_at) VALUES(%s,%s,now()+interval '1 hour')",
                             (digest(token), identity['id']))
            response = RedirectResponse(APP_URL+'/signup', status_code=303)
            response.set_cookie('neighbor_applicant', token, max_age=3600, httponly=True, secure=PRODUCTION, samesite='lax', path='/')
    except Exception as exc:
        logger.warning('Managed sign-in failed: exception=%s', type(exc).__name__)
        response = RedirectResponse(APP_URL+'/?status=expired&error=Sign-in+could+not+be+verified.+Please+try+again.', status_code=303)
    response.delete_cookie('neighbor_cognito', path='/')
    return response


@router.get('/application')
def status(request: Request):
    identity = applicant(request)
    row = one('SELECT status FROM submissions WHERE identity_id=%s ORDER BY created_at DESC LIMIT 1', (identity['id'],))
    existing = one('SELECT id FROM members WHERE email=%s', (identity['email'],))
    return {'email':identity['email'], 'status': row['status'] if row else 'link_required' if existing and not identity['member_id'] else 'new'}


class Application(ProfileInput):
    adult: Literal[True]
    consent: Literal[True]

    @field_validator('adult','consent', mode='before')
    @classmethod
    def explicit_confirmation(cls,value):
        if value is not True: raise ValueError('An explicit confirmation is required.')
        return value


@router.post('/application')
def submit(data: Application, request: Request):
    identity = applicant(request)
    rate_limit('application:'+str(identity['id']), 5)
    if not data.adult or not data.consent:
        raise HTTPException(400, 'Age confirmation and community profile consent are required.')
    validate_zip(data.zip)
    with db() as conn:
        conn.execute('SELECT pg_advisory_xact_lock(hashtext(%s))', (identity['email'],))
        if conn.execute('SELECT id FROM members WHERE email=%s', (identity['email'],)).fetchone():
            raise HTTPException(409, 'An existing membership uses this email. Sign in with Google and link your login from My profile.')
        if conn.execute("SELECT 1 FROM submissions WHERE identity_id=%s AND status='pending'", (identity['id'],)).fetchone():
            return {'status':'pending'}
        value = Submission(version=1, formId='native', responseId=str(uuid4()), email=identity['email'],
            adult=True, consent=True, profile=ProfileInput(**data.model_dump(exclude={'adult','consent'})))
        conn.execute('INSERT INTO submissions(form_id,response_id,email,payload,identity_id) VALUES(%s,%s,%s,%s,%s)',
                     ('native', value.responseId, identity['email'], Jsonb(value.model_dump(mode='json')), identity['id']))
    return {'status':'pending'}
