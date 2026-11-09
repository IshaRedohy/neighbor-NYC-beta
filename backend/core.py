import os
import hashlib
import hmac
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import HTTPException, Request
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / '.env')
PRODUCTION = os.getenv('ENVIRONMENT') == 'production'
APP_URL = os.getenv('APP_URL', 'http://localhost:3000').rstrip('/')
pool = ConnectionPool(os.environ.get('DATABASE_URL', ''), min_size=0, max_size=int(os.getenv('DB_POOL_MAX','2' if PRODUCTION else '8')),
                      max_idle=30, max_lifetime=300, timeout=15 if PRODUCTION else 5, open=False, check=ConnectionPool.check_connection,
                      kwargs={'row_factory': dict_row, 'connect_timeout':10, 'prepare_threshold':None})

def db_open():
    pool.open()

@contextmanager
def db():
    with pool.connection() as conn:
        with conn.transaction():
            yield conn

def query(sql, params=()):
    with db() as conn:
        return conn.execute(sql, params).fetchall()

def one(sql, params=()):
    rows = query(sql, params)
    return rows[0] if rows else None

def demo_enabled():
    return os.getenv('DEMO_MODE') == 'true' and not PRODUCTION

def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()

def signed(body: bytes, timestamp: str, secret: str):
    return hmac.new(secret.encode(), timestamp.encode() + b'.' + body, hashlib.sha256).hexdigest()

def verify_signature(body: bytes, timestamp: str, supplied: str, secret: str, now=None):
    if len(secret) < 32 or len(timestamp) != 13 or not timestamp.isdigit():
        return False
    if abs((now if now is not None else time.time()*1000) - int(timestamp)) > 300000:
        return False
    return hmac.compare_digest(signed(body, timestamp, secret), supplied)

def same_origin(request: Request):
    if request.headers.get('origin') != APP_URL:
        raise HTTPException(403, 'Origin not allowed.')

PUBLIC_FIELDS = '''m.id,m.name,m.zip,m.occupation,m.workplace,m.bio,m.languages,m.cultures,
 m.countries,m.expertise,m.interests,m.needs,m.visible,m.status,m.demo,
 z.borough,z.neighborhood,z.lat,z.lon'''

def member(request: Request, admin=False):
    token = request.cookies.get('neighbor_session')
    if not token:
        raise HTTPException(401, 'Please sign in with an approved account.')
    m = one(f'''SELECT {PUBLIC_FIELDS},m.email,m.role,m.address FROM sessions s JOIN members m ON m.id=s.member_id
        LEFT JOIN zip_codes z ON z.zip=m.zip
        WHERE s.token_hash=%s AND s.expires_at>now() AND m.status='approved' ''', (digest(token),))
    if not m or (m['demo'] and not demo_enabled()):
        raise HTTPException(401, 'Please sign in with an approved account.')
    if admin and m['role'] != 'admin':
        raise HTTPException(403, 'Administrator access required.')
    return m

def rate_limit(key: str, maximum=60):
    row = one('''INSERT INTO rate_limits(key) VALUES(%s) ON CONFLICT(key) DO UPDATE SET
        hits=CASE WHEN rate_limits.window_start<now()-interval '1 minute' THEN 1 ELSE rate_limits.hits+1 END,
        window_start=CASE WHEN rate_limits.window_start<now()-interval '1 minute' THEN now() ELSE rate_limits.window_start END
        RETURNING hits''', (key,))
    if row['hits'] > maximum:
        raise HTTPException(429, 'Too many requests. Try again in a minute.')

async def read_json(request: Request, limit=1048576):
    raw = await limited_body(request, limit)
    import json
    try:
        return json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(400, 'Invalid JSON.')

async def limited_body(request: Request, limit):
    chunks = bytearray()
    async for chunk in request.stream():
        chunks.extend(chunk)
        if len(chunks) > limit:
            raise HTTPException(413, 'Request too large.')
    return bytes(chunks)

def is_blocked(conn, a, b):
    return conn.execute('''SELECT 1 FROM blocks WHERE (blocker_id=%s AND blocked_id=%s)
        OR (blocker_id=%s AND blocked_id=%s)''', (a,b,b,a)).fetchone() is not None
