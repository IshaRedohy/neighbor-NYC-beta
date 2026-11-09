from uuid import UUID
from typing import Literal
from fastapi import APIRouter, Request, HTTPException, Query
from pydantic import BaseModel
from .core import db, query, one, member, rate_limit, demo_enabled, is_blocked
from .models import MessageInput
from .pagination import encode_cursor, decode_cursor

router = APIRouter(prefix='/api')


def access(conn, cid, me):
    c = conn.execute('SELECT * FROM conversations WHERE id=%s AND (sender_id=%s OR recipient_id=%s) FOR UPDATE',
                     (cid, me['id'], me['id'])).fetchone()
    if not c:
        raise HTTPException(404, 'Conversation not found.')
    other = c['recipient_id'] if c['sender_id'] == me['id'] else c['sender_id']
    if is_blocked(conn, me['id'], other):
        raise HTTPException(403, 'Conversation unavailable.')
    return c, other


def insert_message(conn, cid, mid, data):
    # Serialized by conversation lock; uniqueness also protects cross-conversation key reuse.
    row = conn.execute('''INSERT INTO messages(conversation_id,sender_id,body,client_message_id,created_at)
        VALUES(%s,%s,%s,%s,GREATEST(clock_timestamp(),COALESCE(
          (SELECT max(created_at)+interval '1 microsecond' FROM messages WHERE conversation_id=%s),clock_timestamp()))) ON CONFLICT(sender_id,client_message_id)
        WHERE client_message_id IS NOT NULL DO NOTHING RETURNING id,created_at''',
        (cid, mid, data.body, data.clientMessageId, cid)).fetchone()
    if row:
        conn.execute('UPDATE conversations SET updated_at=clock_timestamp() WHERE id=%s', (cid,))
        return {**row, 'duplicate': False}
    existing = conn.execute('SELECT * FROM messages WHERE sender_id=%s AND client_message_id=%s',
                            (mid, data.clientMessageId)).fetchone()
    if existing['conversation_id'] != cid or existing['body'] != data.body:
        raise HTTPException(409, 'This message identifier was already used for different content.')
    return {'id': existing['id'], 'created_at': existing['created_at'], 'duplicate': True}


class StartConversation(MessageInput):
    recipientId: UUID


@router.post('/conversations')
def start(data: StartConversation, request: Request):
    me = member(request)
    rate_limit('requests:' + str(me['id']), 10)
    if data.recipientId == me['id']:
        raise HTTPException(400, 'Choose another member.')
    with db() as conn:
        conn.execute('SELECT pg_advisory_xact_lock(hashtext(%s))', (':'.join(sorted([str(me['id']), str(data.recipientId)])),))
        target = conn.execute("SELECT id FROM members WHERE id=%s AND status='approved' AND visible AND (NOT demo OR %s)",
                              (data.recipientId, demo_enabled())).fetchone()
        if not target or is_blocked(conn, me['id'], data.recipientId):
            raise HTTPException(404, 'Member unavailable.')
        existing = conn.execute('''SELECT id,status FROM conversations WHERE
            LEAST(sender_id,recipient_id)=LEAST(%s::uuid,%s::uuid) AND
            GREATEST(sender_id,recipient_id)=GREATEST(%s::uuid,%s::uuid)''',
            (me['id'], data.recipientId, me['id'], data.recipientId)).fetchone()
        if existing:
            if existing['status'] == 'declined':
                raise HTTPException(403, 'This message request was declined.')
            return {'id': existing['id'], 'existing': True}
        cid = conn.execute('INSERT INTO conversations(sender_id,recipient_id) VALUES(%s,%s) RETURNING id',
                            (me['id'], data.recipientId)).fetchone()['id']
        insert_message(conn, cid, me['id'], data)
    return {'id': cid}


@router.get('/inbox-summary')
def summary(request: Request):
    me = member(request)
    return one('''SELECT count(*)::int AS unread FROM messages msg
        JOIN conversations c ON c.id=msg.conversation_id
        LEFT JOIN conversation_reads r ON r.conversation_id=c.id AND r.member_id=%s
        WHERE (c.sender_id=%s OR c.recipient_id=%s) AND msg.sender_id<>%s
        AND msg.created_at>COALESCE(r.read_at,'1970-01-01'::timestamptz)
        AND NOT EXISTS(SELECT 1 FROM blocks b WHERE
          (b.blocker_id=%s AND b.blocked_id=msg.sender_id) OR (b.blocked_id=%s AND b.blocker_id=msg.sender_id))''', (me['id'],)*6)


@router.get('/conversations')
def conversations(request: Request, before: str = '', limit: int = Query(20, ge=1, le=50)):
    me = member(request)
    cursor = decode_cursor(before)
    rows = query('''SELECT c.*,p.name AS other_name,p.id AS other_id,p.status AS other_status,
        (SELECT body FROM messages WHERE conversation_id=c.id ORDER BY created_at DESC,id DESC LIMIT 1) AS last_message,
        (SELECT count(*) FROM messages msg WHERE msg.conversation_id=c.id AND msg.sender_id<>%s
            AND msg.created_at>COALESCE(r.read_at,'1970-01-01'::timestamptz))::int AS unread
        FROM conversations c JOIN members p ON p.id=CASE WHEN c.sender_id=%s THEN c.recipient_id ELSE c.sender_id END
        LEFT JOIN conversation_reads r ON r.conversation_id=c.id AND r.member_id=%s
        WHERE (c.sender_id=%s OR c.recipient_id=%s)
        AND NOT EXISTS(SELECT 1 FROM blocks b WHERE (b.blocker_id=%s AND b.blocked_id=p.id) OR (b.blocker_id=p.id AND b.blocked_id=%s))
        ''' + ('AND (c.updated_at,c.id)<(%s,%s)' if cursor else '') + ' ORDER BY c.updated_at DESC,c.id DESC LIMIT %s',
        (me['id'],)*7 + (cursor or ()) + (limit+1,))
    return {'conversations': rows[:limit], 'nextCursor': encode_cursor(rows[limit-1], 'updated_at') if len(rows)>limit else None}


@router.get('/conversations/{cid}/messages')
def messages(cid: UUID, request: Request, before: str = '', after: str = '', limit: int = Query(50, ge=1, le=100)):
    if before and after:
        raise HTTPException(400, 'Choose before or after, not both.')
    me = member(request)
    cursor = decode_cursor(before or after)
    with db() as conn:
        c, other = access(conn, cid, me)
        person = conn.execute('SELECT name,status FROM members WHERE id=%s', (other,)).fetchone()
        rows = conn.execute('SELECT * FROM messages WHERE conversation_id=%s' +
            ((' AND (created_at,id)>(%s,%s)' if after else ' AND (created_at,id)<(%s,%s)') if cursor else '') +
            (' ORDER BY created_at,id' if after else ' ORDER BY created_at DESC,id DESC') + ' LIMIT %s',
            (cid,) + (cursor or ()) + (limit+1,)).fetchall()
    page = rows[:limit]
    if not after:
        page.reverse()
    return {'conversation': c, 'other': {**person, 'id': other}, 'messages': page,
            'nextCursor': encode_cursor(rows[limit-1], 'created_at') if len(rows)>limit else None,
            'latestCursor': encode_cursor(page[-1], 'created_at') if page else after or None}


class ReadInput(BaseModel):
    through: UUID


@router.post('/conversations/{cid}/read')
def read(cid: UUID, request: Request, data: ReadInput | None = None):
    me = member(request)
    with db() as conn:
        access(conn, cid, me)
        # Mark only the rendered message as read; a concurrent incoming message stays unread.
        row = conn.execute('SELECT created_at FROM messages WHERE conversation_id=%s' +
            (' AND id=%s' if data else '') + ' ORDER BY created_at DESC,id DESC LIMIT 1',
            (cid, data.through) if data else (cid,)).fetchone()
        if row:
            conn.execute('''INSERT INTO conversation_reads(conversation_id,member_id,read_at) VALUES(%s,%s,%s)
                ON CONFLICT(conversation_id,member_id) DO UPDATE SET read_at=GREATEST(conversation_reads.read_at,EXCLUDED.read_at)''',
                (cid, me['id'], row['created_at']))
    return {'ok': True}


@router.post('/conversations/{cid}/messages')
def send(cid: UUID, data: MessageInput, request: Request):
    me = member(request)
    rate_limit('messages:' + str(me['id']), 30)
    with db() as conn:
        c, other = access(conn, cid, me)
        target = conn.execute('SELECT status FROM members WHERE id=%s', (other,)).fetchone()
        if c['status'] != 'accepted' or target['status'] != 'approved':
            raise HTTPException(403, 'This conversation is not open for messages.')
        return insert_message(conn, cid, me['id'], data)


class Decision(BaseModel):
    action: Literal['accept', 'decline']


@router.post('/conversations/{cid}/decision')
def decide(cid: UUID, data: Decision, request: Request):
    me = member(request)
    with db() as conn:
        c, _ = access(conn, cid, me)
        if c['recipient_id'] != me['id'] or c['status'] != 'pending':
            raise HTTPException(403, 'Only the recipient can respond to a pending request.')
        conn.execute('UPDATE conversations SET status=%s,updated_at=clock_timestamp() WHERE id=%s',
                     ('accepted' if data.action == 'accept' else 'declined', cid))
    return {'ok': True}
