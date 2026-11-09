import os
import json
import logging
from contextlib import asynccontextmanager
from uuid import UUID
from typing import Optional, Literal
from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError, BaseModel, Field, field_validator
from psycopg import OperationalError
from psycopg_pool import PoolTimeout
from .core import (db_open,pool,db,query,one,member,PUBLIC_FIELDS,same_origin,
                   demo_enabled,rate_limit,limited_body,verify_signature,is_blocked,PRODUCTION)
from .models import ProfileInput, MessageInput, distance_miles
from .intake import intake, review_submission, validate_zip
from .auth import router as auth_router
from .graph import graph_candidates
from . import taxonomy

@asynccontextmanager
async def lifespan(app):
    if PRODUCTION and os.getenv('DEMO_MODE')=='true':
        raise RuntimeError('DEMO_MODE must be false in production.')
    db_open()
    yield
    pool.close()
    from .graph import driver
    driver.close()

app=FastAPI(title='NYC Neighbor Hub API',version='0.1.0',lifespan=lifespan,
            docs_url='/api/docs' if not PRODUCTION else None,openapi_url='/api/openapi.json' if not PRODUCTION else None)
app.include_router(auth_router)
from .messaging import router as messaging_router
app.include_router(messaging_router)
from .preferences import router as preferences_router
app.include_router(preferences_router)
from .signup import router as signup_router
app.include_router(signup_router)
from .community import router as community_router
app.include_router(community_router)

@app.middleware('http')
async def security(request: Request, call_next):
    try:
        if request.method in ('POST','PATCH','DELETE','PUT'):
            if request.url.path!='/api/intake/google-forms':
                same_origin(request)
            # Bound request bodies even when Content-Length is absent/chunked.
            request._body=await limited_body(request,1048576)
        response=await call_next(request)
        if request.url.path.startswith('/api/auth/'):
            request.scope['query_string']=b''  # Uvicorn must not log authorization codes.
        if request.method in ('POST','PATCH','PUT','DELETE') and response.status_code<400 and (request.url.path.startswith('/api/me') or request.url.path.startswith('/api/admin/')):
            from .sync_delivery import notify_sync
            from starlette.concurrency import run_in_threadpool
            await run_in_threadpool(notify_sync)
        response.headers['Cache-Control']='no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        return response
    except HTTPException as e:
        return JSONResponse({'error':e.detail},status_code=e.status_code,headers={'Cache-Control':'no-store'})
    except Exception as e:
        logging.getLogger(__name__).error('RequestFailed exception=%s',type(e).__name__)
        request.scope['query_string']=b''
        return JSONResponse({'error':'The service is temporarily unavailable. Please try again shortly.'},status_code=500,headers={'Cache-Control':'no-store'})

@app.exception_handler(HTTPException)
async def http_error(request, exc):
    return JSONResponse({'error':exc.detail},status_code=exc.status_code)

def validation_message(exc):
    return '; '.join('.'.join(str(p) for p in e['loc'])+': '+e['msg'] for e in exc.errors())

@app.exception_handler(RequestValidationError)
@app.exception_handler(ValidationError)
async def invalid(request, exc):
    return JSONResponse({'error':validation_message(exc)},status_code=422)

@app.exception_handler(OperationalError)
@app.exception_handler(PoolTimeout)
async def unavailable(request, exc):
    logging.getLogger(__name__).warning('DatabaseUnavailable exception=%s',type(exc).__name__)
    return JSONResponse({'error':'The service is temporarily unavailable. Please try again shortly.'},status_code=503)

@app.get('/api/config')
def config():
    return {'nativeSignup':os.getenv('NATIVE_SIGNUP')=='true','demo':demo_enabled(),'google':bool(os.getenv('GOOGLE_CLIENT_ID')),'formUrl':
            'https://docs.google.com/forms/d/'+os.environ['GOOGLE_FORM_ID']+'/viewform' if os.getenv('GOOGLE_FORM_ID') else None}

@app.get('/api/health')
def health():
    one('SELECT 1')
    return {'ok':True,'service':'neighbor-hub-python'}

@app.get('/api/me')
def me(request: Request):
    return member(request)

@app.get('/api/zips')
def zips():
    return query('SELECT zip,borough,neighborhood FROM zip_codes ORDER BY zip')

@app.get('/api/discover')
def discover(request: Request, q: str=Query('',max_length=100), language: str=Query('',max_length=60),
             culture: str=Query('',max_length=60), country: str=Query('',max_length=60), interest: str=Query('',max_length=60),
             radius: Literal['same','2','5','all']='all', zip: str=Query('',max_length=5),
             neighborhood: str=Query('',max_length=100), occupation: str=Query('',max_length=100),
             specialty: str=Query('',max_length=60), help: Literal['','receive','give','both']='',
             mode: Literal['recommended','nearby','help_me','i_can_help','shared']='recommended', page: int=Query(1,ge=1,le=10000)):
    me=member(request)
    rows=query(f'''SELECT {PUBLIC_FIELDS} FROM members m JOIN zip_codes z ON z.zip=m.zip
        WHERE m.status='approved' AND m.visible AND m.id<>%s AND (NOT m.demo OR %s)
        AND NOT EXISTS(SELECT 1 FROM blocks b WHERE (b.blocker_id=%s AND b.blocked_id=m.id) OR (b.blocked_id=%s AND b.blocker_id=m.id))
        ORDER BY m.name''',(me['id'],demo_enabled(),me['id'],me['id']))
    available={'countries':sorted({t for p in rows for t in p['countries']}),'languages':sorted({t for p in rows for t in p['languages']}),
               'cultures':sorted({t for p in rows for t in p['cultures']}),
               'interests':sorted({t for p in rows for t in p['interests']})}
    available.update({'occupations':sorted({taxonomy.occupation(p['occupation']) for p in rows}),
        'specialties':sorted({t for p in rows for t in taxonomy.skills(p['expertise'])}),
        'zips':sorted({p['zip'] for p in rows}),'neighborhoods':sorted({p['neighborhood'] for p in rows})})
    preference=one('SELECT shared_culture FROM matching_preferences WHERE member_id=%s',(me['id'],))
    shared_culture=bool(preference and preference['shared_culture'])
    candidates=[]
    for p in rows:
        p['distance']=round(distance_miles(me['lat'],me['lon'],p['lat'],p['lon']),1)
        if radius=='same' and me['zip']!=p['zip']: continue
        if radius not in ('same','all') and p['distance']>float(radius): continue
        if zip and p['zip']!=zip: continue
        if neighborhood and neighborhood.lower()!=p['neighborhood'].lower(): continue
        if occupation and taxonomy.occupation(occupation)!=taxonomy.occupation(p['occupation']): continue
        if specialty and specialty.lower() not in taxonomy.skills(p['expertise']): continue
        can_receive=bool(taxonomy.skills(p['expertise']) & taxonomy.skills(me['needs']))
        can_give=bool(taxonomy.skills(p['needs']) & taxonomy.skills(me['expertise']))
        if (help in ('receive','both') or mode=='help_me') and not can_receive: continue
        if (help in ('give','both') or mode=='i_can_help') and not can_give: continue
        if mode=='nearby' and p['distance']>2: continue
        if mode=='shared' and not (set(p['interests']) & set(me['interests']) or taxonomy.occupation(p['occupation'])==taxonomy.occupation(me['occupation'])): continue
        if language and language.lower() not in p['languages']: continue
        if country and country.lower() not in p['countries']: continue
        if culture and culture.lower() not in p['cultures']: continue
        if interest and interest.lower() not in p['interests']: continue
        if q and q.lower() not in ' '.join([p['name'],p['occupation'],p['bio'],p['zip'],p['neighborhood'],p['borough']]+p['expertise']+p['needs']+p['interests']+p['languages']+p['countries']+p['cultures']).lower(): continue
        candidates.append(p)
    engine='neo4j'
    try:
        if os.getenv('GRAPH_ENABLED','true')!='true': raise RuntimeError('Graph disabled')
        if one('SELECT 1 FROM graph_outbox LIMIT 1'): raise RuntimeError('Graph catching up')
        scores=graph_candidates([str(p['id']) for p in candidates],me) if candidates else {}
        if len(scores)!=len(candidates):
            engine='postgresql'
    except Exception:
        scores={}
        engine='postgresql'
    for p in candidates:
        shared_help=taxonomy.skills(p['expertise']) & taxonomy.skills(me['needs'])
        shared_lang=set(p['languages']) & set(me['languages'])
        shared_interest=set(p['interests']) & set(me['interests'])
        mutual_help=taxonomy.skills(p['needs']) & taxonomy.skills(me['expertise'])
        same_occupation=taxonomy.occupation(p['occupation'])==taxonomy.occupation(me['occupation'])
        score=scores.get(str(p['id'])) if engine=='neo4j' else None
        p['_rank']=(-(score['help'] if score else len(shared_help)),
                    -(score['mutual_help'] if score else len(mutual_help)),p['distance'],
                    -(score['interests'] if score else len(shared_interest)),-(score['languages'] if score else len(shared_lang)),
                    -(score['occupation'] if score else int(same_occupation)),-int(shared_culture and bool(set(p['cultures']) & set(me['cultures']))),p['name'],str(p['id']))
        p['reasons']=([f"Can help with {', '.join(sorted(shared_help))}"] if shared_help else [])
        if mutual_help: p['reasons'].append(f"You can help with {', '.join(sorted(mutual_help))}")
        if same_occupation: p['reasons'].append(f"Shared occupation: {p['occupation']}")
        if shared_interest: p['reasons'].append(f"Shared interests: {', '.join(sorted(shared_interest))}")
        p['reasons']+=([f"You both speak {', '.join(sorted(shared_lang))}"] if shared_lang else [])
        if shared_culture and set(p['cultures']) & set(me['cultures']): p['reasons'].append('Shared culture (your preference)')
        if me['zip']==p['zip']: p['reasons'].append('In your ZIP code')
    candidates.sort(key=lambda p:p['_rank'])
    for p in candidates: del p['_rank']
    return {'profiles':candidates[(page-1)*12:page*12],'total':len(candidates),'page':page,'filters':available,'engine':engine}

@app.get('/api/profiles/{mid}')
def profile(mid: UUID, request: Request):
    me=member(request)
    with db() as conn:
        if is_blocked(conn,me['id'],mid): raise HTTPException(404,'Profile not available.')
        p=conn.execute(f'''SELECT {PUBLIC_FIELDS} FROM members m JOIN zip_codes z ON z.zip=m.zip
            WHERE m.id=%s AND m.status='approved' AND (m.visible OR m.id=%s) AND (NOT m.demo OR %s)''',
            (mid,me['id'],demo_enabled())).fetchone()
    if not p: raise HTTPException(404,'Profile not available.')
    p['distance']=round(distance_miles(me['lat'],me['lon'],p['lat'],p['lon']),1)
    return p

@app.patch('/api/me')
def edit_profile(data: ProfileInput, request: Request):
    me=member(request)
    validate_zip(data.zip)
    with db() as conn:
        conn.execute('''UPDATE members SET name=%s,zip=%s,address=%s,occupation=%s,workplace=%s,bio=%s,languages=%s,
            cultures=%s,countries=%s,expertise=%s,interests=%s,needs=%s,updated_at=now() WHERE id=%s''',
            (data.name,data.zip,data.address,data.occupation,data.workplace,data.bio,data.languages,data.cultures,data.countries,
             data.expertise,data.interests,data.needs,me['id']))
    return {'ok':True}

class Visibility(BaseModel):
    visible: bool

@app.post('/api/me/visibility')
def visibility(data: Visibility,request: Request):
    me=member(request)
    with db() as conn: conn.execute('UPDATE members SET visible=%s,updated_at=now() WHERE id=%s',(data.visible,me['id']))
    return {'ok':True}

@app.delete('/api/me')
def delete_profile(request: Request):
    me=member(request)
    with db() as conn:
        conn.execute('''UPDATE members SET email=NULL,google_sub=NULL,name='Deleted member',zip=NULL,address='',occupation='',workplace='',bio='',
            languages='{}',cultures='{}',countries='{}',expertise='{}',interests='{}',needs='{}',
            visible=false,status='deleted',consent_at=NULL,updated_at=now() WHERE id=%s''',(me['id'],))
        conn.execute('DELETE FROM posts WHERE author_id=%s',(me['id'],))
        conn.execute('DELETE FROM sessions WHERE member_id=%s',(me['id'],))
        conn.execute('DELETE FROM applicant_sessions WHERE identity_id IN (SELECT id FROM login_identities WHERE member_id=%s)',(me['id'],))
        conn.execute("UPDATE login_identities SET email='deleted' WHERE member_id=%s",(me['id'],))
        conn.execute("UPDATE submissions SET payload=NULL,email='deleted',status=CASE WHEN status='pending' THEN 'rejected' ELSE status END WHERE email=%s OR member_id=%s",(me['email'],me['id']))
    return {'ok':True}

@app.post('/api/intake/google-forms')
async def form_intake(request: Request):
    raw=await limited_body(request,32768)
    if not verify_signature(raw,request.headers.get('x-intake-timestamp',''),request.headers.get('x-intake-signature',''),os.getenv('INTAKE_SECRET','')):
        raise HTTPException(401,'Invalid or expired signature.')
    rate_limit('intake',120)
    try: value=json.loads(raw)
    except (ValueError,UnicodeDecodeError): raise HTTPException(400,'Invalid JSON.')
    if not isinstance(value,dict): raise HTTPException(400,'Expected a submission object.')
    if not os.getenv('GOOGLE_FORM_ID') or value.get('formId')!=os.getenv('GOOGLE_FORM_ID'):
        raise HTTPException(403,'Unrecognized form. Configure GOOGLE_FORM_ID.')
    return intake(value)

@app.post('/api/blocks/{mid}')
def block(mid: UUID,request: Request):
    me=member(request)
    if mid==me['id']: raise HTTPException(400,'Cannot block yourself.')
    with db() as conn:
        if not conn.execute('SELECT id FROM members WHERE id=%s',(mid,)).fetchone(): raise HTTPException(404,'Member not found.')
        conn.execute('INSERT INTO blocks(blocker_id,blocked_id) VALUES(%s,%s) ON CONFLICT DO NOTHING',(me['id'],mid))
    return {'ok':True}

@app.get('/api/blocks')
def blocks(request: Request):
    me=member(request)
    return query('SELECT m.id,m.name FROM blocks b JOIN members m ON m.id=b.blocked_id WHERE b.blocker_id=%s',(me['id'],))

@app.delete('/api/blocks/{mid}')
def unblock(mid: UUID,request: Request):
    me=member(request)
    with db() as conn: conn.execute('DELETE FROM blocks WHERE blocker_id=%s AND blocked_id=%s',(me['id'],mid))
    return {'ok':True}

class ReportInput(BaseModel):
    memberId: UUID
    reason: str=Field(min_length=5,max_length=1000)

    @field_validator('reason')
    @classmethod
    def meaningful_reason(cls,value):
        if len(value.strip())<5:
            raise ValueError('Please describe what happened in at least five characters.')
        return value.strip()

@app.post('/api/reports')
def report(data: ReportInput,request: Request):
    me=member(request)
    rate_limit('reports:'+str(me['id']),5)
    if data.memberId==me['id'] or not one('SELECT id FROM members WHERE id=%s',(data.memberId,)):
        raise HTTPException(400,'Choose another member.')
    return one('INSERT INTO reports(reporter_id,reported_id,reason) VALUES(%s,%s,%s) RETURNING id',
               (me['id'],data.memberId,data.reason.strip()))

@app.get('/api/admin')
def admin(request: Request):
    member(request,True)
    from .core import APP_URL
    return {'appUrl':APP_URL,'submissions':query("SELECT s.*,EXISTS(SELECT 1 FROM members m WHERE m.email=s.email) AS existing_member FROM submissions s WHERE s.status='pending' ORDER BY created_at DESC"),
            'members':query("SELECT id,name,email,status,demo FROM members WHERE status<>'deleted' ORDER BY name"),
            'reports':query("SELECT r.*,m.name AS reported_name FROM reports r JOIN members m ON m.id=r.reported_id WHERE r.status='open' ORDER BY r.created_at"),
            'graph':one('SELECT count(*)::int AS pending,COALESCE(max(attempts),0) AS max_attempts FROM graph_outbox')}

class ImportInput(BaseModel):
    submissions: list=Field(max_length=100)

@app.post('/api/admin/import')
def import_submissions(data: ImportInput,request: Request):
    member(request,True)
    results=[]
    for i,value in enumerate(data.submissions):
        try: results.append({'row':i+1,**intake(value)})
        except ValidationError as e: results.append({'row':i+1,'error':validation_message(e)})
        except HTTPException as e: results.append({'row':i+1,'error':e.detail})
    return {'results':results}

class Approval(BaseModel):
    approve: bool

@app.post('/api/admin/submissions/{sid}')
def review(sid: UUID,data: Approval,request: Request):
    member(request,True)
    return review_submission(sid,data.approve)

class MemberStatus(BaseModel):
    status: Literal['approved','suspended']

@app.post('/api/admin/members/{mid}')
def set_status(mid: UUID,data: MemberStatus,request: Request):
    me=member(request,True)
    if mid==me['id']: raise HTTPException(400,'You cannot suspend your own account.')
    with db() as conn:
        row=conn.execute("UPDATE members SET status=%s,updated_at=now() WHERE id=%s AND status<>'deleted' RETURNING id",(data.status,mid)).fetchone()
        if not row: raise HTTPException(404,'Member not found.')
        if data.status=='suspended': conn.execute('DELETE FROM sessions WHERE member_id=%s',(mid,))
    return {'ok':True}

@app.post('/api/admin/reports/{rid}/resolve')
def resolve(rid: UUID,request: Request):
    member(request,True)
    with db() as conn: conn.execute("UPDATE reports SET status='resolved' WHERE id=%s",(rid,))
    return {'ok':True}
