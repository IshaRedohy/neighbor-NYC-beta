import os
from uuid import UUID
from fastapi import HTTPException
from psycopg.types.json import Jsonb
from .core import db, one
from .models import Submission

def validate_zip(zip_code):
    if not one('SELECT zip FROM zip_codes WHERE zip=%s',(zip_code,)):
        raise HTTPException(400, f'ZIP {zip_code} is not in the supported NYC residential ZIP list.')

def intake(value):
    data=Submission.model_validate(value)
    validate_zip(data.profile.zip)
    row=one('''INSERT INTO submissions(form_id,response_id,email,payload) VALUES(%s,%s,%s,%s)
        ON CONFLICT(form_id,response_id) DO NOTHING RETURNING id''',
        (data.formId,data.responseId,str(data.email),Jsonb(data.model_dump(mode='json'))))
    return {'accepted':True,'duplicate':row is None,'id':str(row['id']) if row else None}

def review_submission(submission_id, approve):
    with db() as conn:
        row=conn.execute("SELECT * FROM submissions WHERE id=%s AND status='pending' FOR UPDATE",(submission_id,)).fetchone()
        if not row:
            raise HTTPException(404,'Pending submission not found.')
        if not approve:
            conn.execute("UPDATE submissions SET status='rejected',payload=NULL WHERE id=%s",(submission_id,))
            return {'ok':True}
        data=Submission.model_validate(row['payload'])
        p=data.profile
        # Serialize approvals for the same email, including first-time members.
        conn.execute('SELECT pg_advisory_xact_lock(hashtext(%s))',(str(data.email),))
        existing=conn.execute('SELECT id,status FROM members WHERE email=%s FOR UPDATE',(str(data.email),)).fetchone()
        if existing and existing['status']=='suspended':
            raise HTTPException(409,'Restore the suspended member before approving profile changes.')
        values=(str(data.email),p.name,p.zip,p.address,p.occupation,p.workplace,p.bio,p.languages,p.cultures,p.countries,p.expertise,p.interests,p.needs)
        if existing:
            mid=existing['id']
            conn.execute('''UPDATE members SET name=%s,zip=%s,address=%s,occupation=%s,workplace=%s,bio=%s,languages=%s,
                cultures=%s,countries=%s,expertise=%s,interests=%s,needs=%s,consent_at=now(),updated_at=now()
                WHERE email=%s''',values[1:]+(values[0],))
        else:
            admins=[v.strip().lower() for v in os.getenv('ADMIN_EMAILS','').split(',')]
            role='admin' if str(data.email) in admins else 'member'
            mid=conn.execute('''INSERT INTO members(email,name,zip,address,occupation,workplace,bio,languages,cultures,countries,expertise,interests,needs,status,role,consent_at)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'approved',%s,now()) RETURNING id''',values+(role,)).fetchone()['id']
        conn.execute("UPDATE submissions SET status='approved',member_id=%s,payload=NULL WHERE id=%s",(mid,submission_id))
        return {'ok':True,'memberId':str(mid)}
