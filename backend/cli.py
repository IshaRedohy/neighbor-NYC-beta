import argparse
import json
import sys
from .core import ROOT, db_open, pool, db, demo_enabled

NEIGHBORHOODS={'11372':'Jackson Heights','11103':'Astoria','11211':'Williamsburg','11216':'Bedford-Stuyvesant',
 '10002':'Lower East Side','10027':'Harlem','10451':'Mott Haven','10301':'St. George','11373':'Elmhurst',
 '11218':'Kensington','11432':'Jamaica','10003':'East Village','11201':'Brooklyn Heights','11101':'Long Island City'}

def migrate():
    with db() as conn:
        conn.execute('SELECT pg_advisory_xact_lock(91001)')
        conn.execute('CREATE TABLE IF NOT EXISTS migrations(name text PRIMARY KEY,applied_at timestamptz DEFAULT now())')
        for migration in sorted((ROOT/'db').glob('*.sql')):
            if not conn.execute('SELECT name FROM migrations WHERE name=%s',(migration.stem,)).fetchone():
                conn.execute(migration.read_text())
                conn.execute('INSERT INTO migrations(name) VALUES(%s)',(migration.stem,))
        for row in json.loads((ROOT/'data/nyc-zips.json').read_text()):
            zip_code=row['zcta5']
            borough='Staten Island' if zip_code.startswith('103') else 'Bronx' if zip_code.startswith('104') else 'Brooklyn' if zip_code.startswith('112') else 'Queens' if zip_code.startswith(('110','111','113','114','116')) else 'Manhattan'
            conn.execute('''INSERT INTO zip_codes(zip,borough,neighborhood,lat,lon) VALUES(%s,%s,%s,%s,%s)
                ON CONFLICT(zip) DO UPDATE SET lat=EXCLUDED.lat,lon=EXCLUDED.lon,borough=EXCLUDED.borough,neighborhood=EXCLUDED.neighborhood''',
                (zip_code,borough,NEIGHBORHOODS.get(zip_code,borough),float(row['centlat']),float(row['centlon'])))
    print('Migrations and NYC ZIP reference loaded.')

def seed():
    if not demo_enabled(): raise RuntimeError('Seeding requires DEMO_MODE=true and ENVIRONMENT=development.')
    fixtures=json.loads((ROOT/'data/demo-members.json').read_text())
    with db() as conn:
        for p in fixtures:
            conn.execute('''INSERT INTO members(email,name,zip,occupation,workplace,bio,languages,cultures,countries,expertise,interests,needs,status,role,demo,consent_at)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'approved',%s,true,now()) ON CONFLICT(email) DO NOTHING''',
                (p['email'],p['name'],p['zip'],p['occupation'],p['workplace'],p['bio'],p['languages'],p['cultures'],p['countries'],p['expertise'],p['interests'],p['needs'],p.get('role','member')))
    print('12 fictional demo profiles ready. Existing profiles were not overwritten.')

def bootstrap(email):
    from .intake import intake,review_submission
    # Explicit local-owner bootstrap, no public route for granting administrator access.
    result=intake({'version':1,'formId':'local-bootstrap','responseId':email,'email':email,'consent':True,'adult':True,
        'profile':{'name':'Community host','zip':'11372','occupation':'Community organizer','languages':['english'],'expertise':['community building']}})
    if result['id']: review_submission(result['id'],True)
    with db() as conn:
        conn.execute("UPDATE members SET role='admin' WHERE email=%s AND status='approved'",(email.lower(),))
    print('Administrator account ready. Sign in with this Google account.')

def main():
    parser=argparse.ArgumentParser(description='Neighbor Hub local tools')
    parser.add_argument('command',choices=['migrate','seed','sync','worker','rebuild','bootstrap-admin'])
    parser.add_argument('--email')
    args=parser.parse_args()
    db_open()
    try:
        if args.command=='migrate': migrate()
        elif args.command=='seed': seed()
        elif args.command=='bootstrap-admin':
            if not args.email: parser.error('--email is required')
            bootstrap(args.email)
        else:
            from .graph import constraints,sync_batch,worker,rebuild,driver
            try:
                if args.command=='sync':
                    constraints()
                    print('Synced',sync_batch(),'profiles.')
                elif args.command=='rebuild': rebuild()
                else: worker()
            finally: driver.close()
    finally: pool.close()

if __name__=='__main__': main()
