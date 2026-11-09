import os
import time
from neo4j import GraphDatabase
from .core import db, query
from . import taxonomy

driver=GraphDatabase.driver(os.getenv('NEO4J_URI','bolt://127.0.0.1:7687'),
    auth=(os.getenv('NEO4J_USER','neo4j'),os.getenv('NEO4J_PASSWORD','')),connection_timeout=3,
    connection_acquisition_timeout=3,max_transaction_retry_time=2)

def constraints():
    for label,field in [('Person','id'),('Zip','code'),('Neighborhood','key'),('Occupation','name'),('Language','name'),('Culture','name'),('Country','name'),('Expertise','name'),('Interest','name')]:
        driver.execute_query(f'CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) REQUIRE n.{field} IS UNIQUE',database_='neo4j')

def sync_batch(limit=50, budget_seconds=90):
    deadline=time.monotonic()+budget_seconds
    processed=0
    with db() as conn:
        # Single worker across processes; retain outbox entries if a member changes during sync.
        if not conn.execute('SELECT pg_try_advisory_xact_lock(91002) AS locked').fetchone()['locked']:
            return 0
        jobs=conn.execute('SELECT * FROM graph_outbox WHERE available_at<=now() ORDER BY updated_at LIMIT %s',(limit,)).fetchall()
        for job in jobs:
            if time.monotonic()>=deadline: break
            member=conn.execute('SELECT m.*,z.lat,z.lon,z.neighborhood,z.borough FROM members m LEFT JOIN zip_codes z ON z.zip=m.zip WHERE m.id=%s',(job['member_id'],)).fetchone()
            mid=str(job['member_id'])
            try:
                def update(tx):
                    tx.run('MATCH (p:Person {id:$id}) DETACH DELETE p',id=mid).consume()
                    if not member or member['status']!='approved' or not member['visible']:
                        return
                    tx.run('''CREATE (p:Person {id:$id, name:$name, demo:$demo, projection_version:3,
                            zip:$zip, lat:$lat, lon:$lon})
                        MERGE (z:Zip {code:$zip}) SET z.borough=$borough
                        MERGE (p)-[:LIVES_IN]->(z)
                        MERGE (o:Occupation {name:$occupation}) MERGE (p)-[:WORKS_AS]->(o)''',
                        id=mid,name=member['name'],demo=member['demo'],zip=member['zip'],
                        lat=member['lat'],lon=member['lon'],borough=member['borough'],
                        occupation=taxonomy.occupation(member['occupation'])).consume()
                    # Unmapped ZIPs use borough as their SQL display label, not a neighborhood.
                    if member['neighborhood'] and member['neighborhood']!=member['borough']:
                        tx.run('''MATCH (p:Person {id:$id})-[:LIVES_IN]->(z:Zip)
                            MERGE (n:Neighborhood {key:$key}) SET n.name=$name,n.borough=$borough
                            MERGE (z)-[:IN_NEIGHBORHOOD]->(n)''',id=mid,
                            key=member['borough']+':'+member['neighborhood'],
                            name=member['neighborhood'],borough=member['borough']).consume()
                    for field,label,rel in [('languages','Language','SPEAKS'),('cultures','Culture','IDENTIFIES_WITH'),
                        ('countries','Country','FROM'),('expertise','Expertise','CAN_HELP_WITH'),('interests','Interest','INTERESTED_IN'),('needs','Expertise','NEEDS_HELP_WITH')]:
                        tx.run(f'''MATCH (p:Person {{id:$id}}) UNWIND $values AS value
                            MERGE (t:{label} {{name:value}}) MERGE (p)-[:{rel}]->(t)''',id=mid,values=sorted(taxonomy.skills(member[field])) if field in ('expertise','needs') else member[field]).consume()
                    # A need and an offered skill share one concept so matching is a direct path.
                    tx.run('''MATCH (p:Person {id:$id})-[:NEEDS_HELP_WITH]->(t:Expertise)
                        SET t:Need''',id=mid).consume()
                with driver.session(database='neo4j') as session:
                    session.execute_write(update)
                conn.execute('DELETE FROM graph_outbox WHERE member_id=%s AND version=%s',(mid,job['version']))
                processed+=1
            except Exception as e:
                delay=min(300,2**min(job['attempts']+1,8))
                conn.execute('''UPDATE graph_outbox SET attempts=attempts+1,available_at=now()+make_interval(secs=>%s),last_error=%s
                    WHERE member_id=%s AND version=%s''',(delay,type(e).__name__,mid,job['version']))
    return processed

def graph_candidates(ids, me):
    result=driver.execute_query('''MATCH (p:Person) WHERE p.id IN $ids AND p.projection_version=3
        OPTIONAL MATCH (p)-[:CAN_HELP_WITH]->(skill:Expertise)
        WITH p,count(CASE WHEN skill.name IN $needs THEN 1 END) AS help
        OPTIONAL MATCH (p)-[:SPEAKS]->(language:Language)
        WITH p,help,count(CASE WHEN language.name IN $languages THEN 1 END) AS languages
        OPTIONAL MATCH (p)-[:INTERESTED_IN]->(interest:Interest)
        WITH p,help,languages,count(CASE WHEN interest.name IN $interests THEN 1 END) AS interests
        OPTIONAL MATCH (p)-[:NEEDS_HELP_WITH]->(need:Expertise)
        WITH p,help,languages,interests,count(CASE WHEN need.name IN $expertise THEN 1 END) AS mutual_help
        OPTIONAL MATCH (p)-[:WORKS_AS]->(occupation:Occupation)
        RETURN p.id AS id,help,languages,interests,mutual_help,
            count(CASE WHEN occupation.name=$occupation THEN 1 END) AS occupation''',
        ids=ids,needs=sorted(taxonomy.skills(me['needs'])),languages=me['languages'],interests=me['interests'],
        expertise=sorted(taxonomy.skills(me['expertise'])),occupation=taxonomy.occupation(me['occupation']),database_='neo4j')
    return {r['id']:{key:r[key] for key in ('help','languages','interests','mutual_help','occupation')} for r in result.records}

def rebuild():
    # Only deletes this application's Person nodes, not arbitrary graph data.
    driver.execute_query('MATCH (p:Person) DETACH DELETE p',database_='neo4j')
    with db() as conn:
        conn.execute('''INSERT INTO graph_outbox(member_id) SELECT id FROM members
            ON CONFLICT(member_id) DO UPDATE SET version=graph_outbox.version+1,attempts=0,available_at=now()''')
    constraints()
    while sync_batch():
        pass

def worker():
    while True:
        try:
            constraints()
            sync_batch()
            with db() as conn:
                conn.execute('DELETE FROM sessions WHERE expires_at<now()')
                conn.execute("DELETE FROM rate_limits WHERE window_start<now()-interval '1 day'")
        except Exception as e:
            print('Sync retry:',type(e).__name__,flush=True)
        time.sleep(5)
