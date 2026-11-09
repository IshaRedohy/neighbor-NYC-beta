from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict
from .core import member, one

router = APIRouter(prefix='/api')

class Preferences(BaseModel):
    model_config = ConfigDict(extra='forbid')
    sharedCulture: bool = False

@router.get('/preferences')
def get_preferences(request: Request):
    me = member(request)
    row = one('SELECT shared_culture FROM matching_preferences WHERE member_id=%s', (me['id'],))
    return {'sharedCulture': bool(row and row['shared_culture'])}

@router.put('/preferences')
def save_preferences(data: Preferences, request: Request):
    me = member(request)
    one('''INSERT INTO matching_preferences(member_id,shared_culture) VALUES(%s,%s)
        ON CONFLICT(member_id) DO UPDATE SET shared_culture=EXCLUDED.shared_culture,updated_at=now() RETURNING member_id''',
        (me['id'], data.sharedCulture))
    return data

@router.get('/suggestions')
def suggestions(request: Request):
    member(request)
    from .taxonomy import OCCUPATIONS, SKILLS
    return {'occupations': sorted(set(OCCUPATIONS.values())), 'skills': sorted(set(SKILLS.values()) | {'career advice','construction','business','translation'})}
