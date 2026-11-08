from datetime import datetime, timezone
from typing import Literal, Optional, List
from uuid import UUID
from fastapi import APIRouter, Request, Query, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from .core import member, query, db, demo_enabled, rate_limit
from .models import distance_miles, ProfileInput
from .intake import validate_zip

router = APIRouter(prefix='/api')

class PostInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    kind: Literal['need','offer','event']
    title: str = Field(min_length=3,max_length=120)
    body: str = Field(min_length=5,max_length=2000)
    tags: List[str] = Field(min_length=1,max_length=12)
    zip: str = Field(pattern=r'^\d{5}$')
    starts_at: Optional[datetime] = None
    venue: str = Field(default='',max_length=160)

    @field_validator('tags')
    @classmethod
    def normalize_tags(cls, values):
        return ProfileInput.normalize(values)

    @model_validator(mode='after')
    def event_details(self):
        if self.kind == 'event':
            if not self.starts_at or not self.starts_at.tzinfo or self.starts_at <= datetime.now(timezone.utc):
                raise ValueError('Events need a future date and time with timezone.')
            if not self.venue:
                raise ValueError('Events need a public meeting place.')
        elif self.starts_at is not None or self.venue:
            raise ValueError('Only events have a start time and venue.')
        return self

def matches(tags, viewer):
    values = viewer['interests'] + viewer['expertise'] + viewer['needs'] + [viewer['occupation'].lower()]
    return sorted({tag for tag in tags if any(tag in value or value in tag for value in values if value)})

def visible_posts(viewer, radius='5'):
    rows=query('''SELECT p.*,m.name,z.neighborhood,z.borough,z.lat,z.lon,
        EXISTS(SELECT 1 FROM event_reads r WHERE r.post_id=p.id AND r.member_id=%s) AS seen
        FROM posts p JOIN members m ON m.id=p.author_id JOIN zip_codes z ON z.zip=p.zip
        WHERE m.status='approved' AND m.visible AND (NOT m.demo OR %s)
        AND (p.starts_at IS NULL OR p.starts_at>now())
        AND NOT EXISTS(SELECT 1 FROM blocks b WHERE
        (b.blocker_id=%s AND b.blocked_id=m.id) OR (b.blocked_id=%s AND b.blocker_id=m.id))
        ORDER BY p.created_at DESC''',(viewer['id'],demo_enabled(),viewer['id'],viewer['id']))
    result=[]
    for row in rows:
        distance=distance_miles(viewer['lat'],viewer['lon'],row.pop('lat'),row.pop('lon'))
        if radius!='all' and distance>float(radius): continue
        row['distance']=round(distance,1)
        row['matches']=matches(row['tags'],viewer)
        result.append(row)
    return result

@router.post('/posts')
def create_post(data: PostInput, request: Request):
    viewer=member(request)
    if not viewer['visible']: raise HTTPException(403,'Show your profile before publishing to the community.')
    rate_limit('posts:'+str(viewer['id']),10)
    validate_zip(data.zip)
    with db() as conn:
        return conn.execute('''INSERT INTO posts(author_id,kind,title,body,tags,zip,starts_at,venue)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
            (viewer['id'],data.kind,data.title,data.body,data.tags,data.zip,data.starts_at,data.venue)).fetchone()

@router.get('/posts')
def feed(request: Request, radius: Literal['2','5','all']='5', kind: Literal['all','need','offer','event']='all',
         relevant: bool=False, page: int=Query(1,ge=1)):
    viewer=member(request)
    rows=[p for p in visible_posts(viewer,radius) if (kind=='all' or p['kind']==kind)
          and (not relevant or p['matches'] or p['kind']=='event' or p['author_id']==viewer['id'])]
    rows.sort(key=lambda p: not bool(p['matches']))
    return {'posts':rows[(page-1)*20:page*20],'total':len(rows)}

@router.delete('/posts/{pid}')
def delete_post(pid: UUID, request: Request):
    viewer=member(request)
    with db() as conn:
        row=conn.execute('DELETE FROM posts WHERE id=%s AND (author_id=%s OR %s) RETURNING id',
                         (pid,viewer['id'],viewer['role']=='admin')).fetchone()
        if not row: raise HTTPException(404,'Post not available.')
    return {'ok':True}

@router.get('/notifications')
def notifications(request: Request):
    viewer=member(request)
    rows=[p for p in visible_posts(viewer) if p['kind']=='event' and not p['seen'] and p['author_id']!=viewer['id']]
    return {'count':len(rows),'events':rows}

@router.post('/notifications/{pid}/read')
def read_notification(pid: UUID, request: Request):
    viewer=member(request)
    if not any(p['id']==pid and p['kind']=='event' for p in visible_posts(viewer)):
        raise HTTPException(404,'Event not available.')
    with db() as conn:
        conn.execute('INSERT INTO event_reads(member_id,post_id) VALUES(%s,%s) ON CONFLICT DO NOTHING',(viewer['id'],pid))
    return {'ok':True}
