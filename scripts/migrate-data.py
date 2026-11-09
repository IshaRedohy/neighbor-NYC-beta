"""Copy real community data to an empty migrated database, keeping UUIDs and roles.
Use while writes are paused. A single source snapshot and target transaction prevent partial migration.
"""
import argparse
from dotenv import dotenv_values
import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

parser=argparse.ArgumentParser()
parser.add_argument('--source-env',required=True)
parser.add_argument('--target-env',required=True)
args=parser.parse_args()
def url(file):
    values=dotenv_values(file)
    return values.get('DIRECT_DATABASE_URL') or values['DATABASE_URL']
source_url,target_url=url(args.source_env),url(args.target_env)
if source_url==target_url: raise SystemExit('Source and target must differ.')
real='SELECT id FROM members WHERE NOT demo'
convos=f'SELECT id FROM conversations WHERE sender_id IN ({real}) AND recipient_id IN ({real})'
posts=f'SELECT id FROM posts WHERE author_id IN ({real})'
tables=[('members','NOT demo'),('login_identities',f'member_id IN ({real})'),
 ('submissions',f"member_id IN ({real}) AND (identity_id IS NULL OR identity_id IN (SELECT id FROM login_identities WHERE member_id IN ({real})))"),
 ('matching_preferences',f'member_id IN ({real})'),('conversations',f'id IN ({convos})'),
 ('messages',f'conversation_id IN ({convos})'),('conversation_reads',f'conversation_id IN ({convos}) AND member_id IN ({real})'),
 ('blocks',f'blocker_id IN ({real}) AND blocked_id IN ({real})'),('reports',f'reporter_id IN ({real}) AND reported_id IN ({real})'),
 ('posts',f'id IN ({posts})'),('event_reads',f'post_id IN ({posts}) AND member_id IN ({real})')]
with psycopg.connect(source_url,row_factory=dict_row) as source, psycopg.connect(target_url,row_factory=dict_row) as target:
    source.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
    target.execute('SELECT pg_advisory_xact_lock(91001)')
    if target.execute('SELECT 1 FROM members LIMIT 1').fetchone():
        raise SystemExit('Target already contains members; refusing to overwrite or merge.')
    for table,where in tables:
        rows=source.execute(sql.SQL('SELECT * FROM {} WHERE '+where).format(sql.Identifier(table))).fetchall()
        for row in rows:
            keys=list(row)
            values=[Jsonb(row[k]) if isinstance(row[k],dict) else row[k] for k in keys]
            target.execute(sql.SQL('INSERT INTO {} ({}) VALUES ({})').format(sql.Identifier(table),
                sql.SQL(',').join(map(sql.Identifier,keys)),sql.SQL(',').join(sql.Placeholder() for _ in keys)),values)
        print(table+':',len(rows),'copied')
    # Sessions, rate limits, and OAuth attempts intentionally do not migrate.
    # Pending form applications are re-imported from the original private export after migration.
print('Migration committed; demo members excluded. Sign in again on the hosted domain.')
