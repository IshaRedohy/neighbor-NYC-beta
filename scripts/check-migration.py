"""Exercise the real-data migration using only isolated synthetic databases."""
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4
import psycopg
from psycopg.rows import dict_row

source='postgresql://neighbor:test-only-password@127.0.0.1:15432/neighborhub_test'
target=source.replace('/neighborhub_test','/neighborhub_migration_test')
with psycopg.connect(source.replace('/neighborhub_test','/postgres'),autocommit=True) as conn:
    conn.execute('DROP DATABASE IF EXISTS neighborhub_migration_test')
    conn.execute('CREATE DATABASE neighborhub_migration_test')
with psycopg.connect(source) as conn:
    ids=[]
    for role in ['admin','member']:
        ids.append(conn.execute("INSERT INTO members(email,name,zip,status,role,demo) VALUES(%s,'Synthetic migration profile','11368','approved',%s,false) RETURNING id",(uuid4().hex+'@example.com',role)).fetchone()[0])
    cid=conn.execute("INSERT INTO conversations(sender_id,recipient_id,status) VALUES(%s,%s,'accepted') RETURNING id",ids).fetchone()[0]
    conn.execute("INSERT INTO messages(conversation_id,sender_id,body) VALUES(%s,%s,'Synthetic migration message')",(cid,ids[0]))
subprocess.run([sys.executable,'-m','backend.cli','migrate'],check=True,env={**os.environ,'DATABASE_URL':target,'ENVIRONMENT':'development','DEMO_MODE':'false'})
Path('.artifacts').mkdir(exist_ok=True)
for name,value in [('source',source),('target',target)]:
    file=Path('.artifacts/migration-'+name+'.env')
    file.write_text('DIRECT_DATABASE_URL='+value+'\n');file.chmod(0o600)
subprocess.run([sys.executable,'scripts/migrate-data.py','--source-env','.artifacts/migration-source.env','--target-env','.artifacts/migration-target.env'],check=True)
with psycopg.connect(source,row_factory=dict_row) as src,psycopg.connect(target,row_factory=dict_row) as dst:
    assert src.execute('SELECT * FROM members WHERE NOT demo ORDER BY id').fetchall()==dst.execute('SELECT * FROM members ORDER BY id').fetchall()
    assert dst.execute('SELECT count(*) AS n FROM members WHERE demo').fetchone()['n']==0
    assert dst.execute('SELECT count(*) AS n FROM messages WHERE conversation_id=%s',(cid,)).fetchone()['n']==1
    assert dst.execute('SELECT count(*) AS n FROM sessions').fetchone()['n']==0
    assert dst.execute('SELECT count(*) AS n FROM graph_outbox').fetchone()['n']==dst.execute('SELECT count(*) AS n FROM members').fetchone()['n']
print('Migration verified: UUIDs, roles and profiles preserved; messages copied; demo accounts and sessions excluded.')
