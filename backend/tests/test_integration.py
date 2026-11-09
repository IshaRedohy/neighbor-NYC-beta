import os
import json
import time
import unittest
from unittest.mock import patch
from uuid import uuid4
from fastapi.testclient import TestClient

@unittest.skipUnless(os.getenv('RUN_INTEGRATION')=='1','Set RUN_INTEGRATION=1 with an isolated neighborhub_test database.')
class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from backend.core import pool
        if not os.environ.get('DATABASE_URL','').endswith('/neighborhub_test'):
            raise RuntimeError('Integration tests only run against the dedicated neighborhub_test database.')
        from backend.main import app
        from backend.cli import migrate,seed
        cls.client_context=TestClient(app)
        cls.client=cls.client_context.__enter__()
        if os.getenv('NEO4J_URI')!='bolt://127.0.0.1:17687':
            raise RuntimeError('Integration tests require the isolated Neo4j from compose.test.yaml on port 17687.')
        migrate()
        from backend.core import db
        with db() as conn:
            conn.execute('TRUNCATE members,login_identities,submissions,rate_limits,oauth_attempts CASCADE')
        seed()
        # Each previous run removes only its test graph projection. Requeue all
        # isolated SQL fixtures so repeated runs start with a rebuildable graph.
        with db() as conn:
            conn.execute('''INSERT INTO graph_outbox(member_id) SELECT id FROM members
                ON CONFLICT(member_id) DO UPDATE SET version=graph_outbox.version+1,attempts=0,available_at=now()''')
        cls.origin={'origin':'http://localhost:3000'}

    @classmethod
    def tearDownClass(cls):
        from backend.core import query
        from backend.graph import driver
        ids=[str(r['id']) for r in query('SELECT id FROM members')]
        driver.execute_query('MATCH (p:Person) WHERE p.id IN $ids DETACH DELETE p',ids=ids,database_='neo4j')
        cls.client_context.__exit__(None,None,None)

    def setUp(self):
        self.client.cookies.clear()

    def login(self,email='maya@example.com'):
        response=self.client.post('/api/auth/demo',json={'email':email},headers=self.origin)
        self.assertEqual(response.status_code,200,response.text)
        return self.client.get('/api/me').json()

    def submission(self):
        suffix=uuid4().hex[:12]
        return {'version':1,'formId':'test-form','responseId':suffix,'email':suffix+'@example.com',
            'consent':True,'adult':True,'profile':{'name':'Test Neighbor '+suffix,'zip':'11372','occupation':'Designer',
            'languages':['English'],'expertise':['career advice'],'interests':['technology'],'bio':'A fictional test profile.'}}

    def test_access_and_csrf(self):
        self.assertEqual(self.client.get('/api/discover').status_code,401)
        self.assertEqual(self.client.post('/api/auth/demo',json={'email':'maya@example.com'}).status_code,403)
        self.login('arif@example.com')
        self.assertEqual(self.client.get('/api/admin').status_code,403)
        self.assertNotIn('email',self.client.get('/api/discover?radius=all').json()['profiles'][0])

    def test_discovery_filters_and_fallback(self):
        self.login()
        with patch('backend.main.graph_candidates',side_effect=RuntimeError('offline')):
            result=self.client.get('/api/discover?radius=all&language=bengali').json()
            self.assertEqual(result['engine'],'postgresql')
            self.assertTrue(all('bengali' in p['languages'] for p in result['profiles']))
            self.assertTrue(result['total']>=2)
        same=self.client.get('/api/discover?radius=same').json()['profiles']
        self.assertTrue(all(p['zip']=='11372' for p in same))
        result=self.client.get('/api/discover?radius=all&q=web%20development').json()['profiles']
        self.assertTrue(any(p['name']=='Arif Chowdhury' for p in result))
        result=self.client.get('/api/discover?radius=all&country=bangladesh').json()
        self.assertGreater(result['total'],0)
        self.assertTrue(all('bangladesh' in p['countries'] for p in result['profiles']))
        result=self.client.get('/api/discover?radius=all&q=technology').json()['profiles']
        self.assertTrue(any('technology' in p['interests'] for p in result))

    def test_intake_approval_duplicate_and_invalid(self):
        self.login()
        data=self.submission()
        response=self.client.post('/api/admin/import',json={'submissions':[data,data,{**data,'responseId':'bad','profile':{**data['profile'],'zip':'90210'}}]},headers=self.origin)
        rows=response.json()['results']
        self.assertTrue(rows[0]['accepted']);self.assertTrue(rows[1]['duplicate']);self.assertIn('error',rows[2])
        sid=rows[0]['id']
        pending=self.client.get('/api/discover?radius=all&q='+data['profile']['name']).json()
        self.assertEqual(pending['total'],0)
        approved=self.client.post('/api/admin/submissions/'+sid,json={'approve':True},headers=self.origin)
        self.assertEqual(approved.status_code,200,approved.text)
        mid=approved.json()['memberId']
        self.assertEqual(self.client.get('/api/profiles/'+mid).status_code,200)
        self.assertEqual(self.client.post('/api/admin/submissions/'+sid,json={'approve':True},headers=self.origin).status_code,404)
        duplicate_email={**data,'responseId':uuid4().hex,'profile':{**data['profile'],'name':'Updated test name'}}
        self.client.post('/api/admin/import',json={'submissions':[duplicate_email]},headers=self.origin)
        self.assertEqual(self.client.get('/api/profiles/'+mid).json()['name'],data['profile']['name'])

    def test_signed_webhook(self):
        from backend.core import signed
        data=self.submission();body=json.dumps(data).encode();stamp=str(int(time.time()*1000));secret='s'*40
        headers={'content-type':'application/json','x-intake-timestamp':stamp,'x-intake-signature':signed(body,stamp,secret)}
        with patch.dict(os.environ,{'INTAKE_SECRET':secret,'GOOGLE_FORM_ID':'test-form'}):
            response=self.client.post('/api/intake/google-forms',content=body,headers=headers)
            self.assertEqual(response.status_code,200,response.text)
            self.assertTrue(self.client.post('/api/intake/google-forms',content=body,headers=headers).json()['duplicate'])
            self.assertEqual(self.client.post('/api/intake/google-forms',content=body+b' ',headers=headers).status_code,401)
            headers['x-intake-timestamp']=str(int(stamp)-600000)
            headers['x-intake-signature']=signed(body,headers['x-intake-timestamp'],secret)
            self.assertEqual(self.client.post('/api/intake/google-forms',content=body,headers=headers).status_code,401)

    def test_message_request_accept_privacy_and_block(self):
        from backend.core import db
        maya=self.login()
        arif=next(p for p in self.client.get('/api/discover?radius=all').json()['profiles'] if p['name']=='Arif Chowdhury')
        # A new isolated pair for each test invocation avoids changing real/demo conversations.
        with db() as conn:
            target=conn.execute("INSERT INTO members(email,name,zip,occupation,languages,expertise,status,demo) VALUES(%s,'Message Test','11372','Tester',ARRAY['english'],ARRAY['testing'],'approved',true) RETURNING id",(uuid4().hex+'@example.com',)).fetchone()
            email=conn.execute('SELECT email FROM members WHERE id=%s',(target['id'],)).fetchone()['email']
        cid=self.client.post('/api/conversations',json={'recipientId':str(target['id']),'body':'Hello neighbor'},headers=self.origin).json()['id']
        self.assertEqual(self.client.post('/api/conversations/'+cid+'/messages',json={'body':'Too soon'},headers=self.origin).status_code,403)
        self.assertEqual(self.client.post('/api/conversations/'+cid+'/decision',json={'action':'accept'},headers=self.origin).status_code,403)
        self.login('arif@example.com')
        self.assertEqual(self.client.get('/api/conversations/'+cid+'/messages').status_code,404)
        self.login(email)
        self.assertTrue(next(t for t in self.client.get('/api/conversations').json()['conversations'] if t['id']==cid)['unread']>0)
        self.assertEqual(self.client.post('/api/conversations/'+cid+'/decision',json={'action':'accept'},headers=self.origin).status_code,200)
        self.assertEqual(self.client.post('/api/conversations/'+cid+'/messages',json={'body':'Happy to help'},headers=self.origin).status_code,200)
        self.client.post('/api/conversations/'+cid+'/read',headers=self.origin)
        self.assertEqual(next(t for t in self.client.get('/api/conversations').json()['conversations'] if t['id']==cid)['unread'],0)
        self.client.post('/api/blocks/'+maya['id'],headers=self.origin)
        self.assertEqual(self.client.get('/api/profiles/'+maya['id']).status_code,404)
        self.assertEqual(self.client.post('/api/conversations/'+cid+'/messages',json={'body':'Blocked'},headers=self.origin).status_code,403)
        self.login()
        self.assertEqual(self.client.get('/api/profiles/'+str(target['id'])).status_code,404)
        self.assertFalse(any(t['id']==cid for t in self.client.get('/api/conversations').json()['conversations']))

    def test_visibility_and_deletion(self):
        from backend.core import db,one
        self.login()
        data=self.submission()
        sid=self.client.post('/api/admin/import',json={'submissions':[data]},headers=self.origin).json()['results'][0]['id']
        mid=self.client.post('/api/admin/submissions/'+sid,json={'approve':True},headers=self.origin).json()['memberId']
        with db() as conn: conn.execute('UPDATE members SET demo=true WHERE id=%s',(mid,))
        self.login(data['email'])
        self.client.post('/api/me/visibility',json={'visible':False},headers=self.origin)
        self.login()
        self.assertEqual(self.client.get('/api/profiles/'+mid).status_code,404)
        self.login(data['email'])
        self.assertEqual(self.client.delete('/api/me',headers=self.origin).status_code,200)
        self.assertEqual(self.client.get('/api/me').status_code,401)
        deleted=one('SELECT * FROM members WHERE id=%s',(mid,))
        self.assertIsNone(deleted['email']);self.assertEqual(deleted['name'],'Deleted member')
        self.assertIsNotNone(one('SELECT 1 FROM graph_outbox WHERE member_id=%s',(mid,)))

    def test_production_demo_route_rejected(self):
        with patch('backend.core.PRODUCTION',True):
            self.assertEqual(self.client.post('/api/auth/demo',json={'email':'maya@example.com'},headers=self.origin).status_code,404)

    def test_graph_sync_recovery_and_visibility(self):
        from backend.graph import constraints,sync_batch,driver
        from backend.core import db,one
        constraints()
        with db() as conn:
            conn.execute('UPDATE graph_outbox SET available_at=now()')
        while sync_batch(): pass
        me=self.login()
        records=driver.execute_query('MATCH (p:Person {id:$id})-[:SPEAKS]->(l:Language) RETURN l.name AS language',id=me['id'],database_='neo4j').records
        self.assertTrue(any(r['language']=='bengali' for r in records))
        node=driver.execute_query('MATCH (p:Person {id:$id}) RETURN properties(p) AS p',id=me['id'],database_='neo4j').records[0]['p']
        self.assertNotIn('email',node)
        self.client.post('/api/me/visibility',json={'visible':False},headers=self.origin)
        with patch('backend.graph.driver.session',side_effect=RuntimeError('offline')):
            sync_batch()
        self.assertGreater(one('SELECT attempts FROM graph_outbox WHERE member_id=%s',(me['id'],))['attempts'],0)
        with db() as conn: conn.execute('UPDATE graph_outbox SET available_at=now()')
        sync_batch()
        self.assertEqual(len(driver.execute_query('MATCH (p:Person {id:$id}) RETURN p',id=me['id'],database_='neo4j').records),0)
        self.client.post('/api/me/visibility',json={'visible':True},headers=self.origin)
        sync_batch()
        self.assertEqual(len(driver.execute_query('MATCH (p:Person {id:$id}) RETURN p',id=me['id'],database_='neo4j').records),1)

    def test_graph_relationships_and_recommendation_parity(self):
        from backend.graph import constraints,sync_batch,driver,graph_candidates
        from backend.core import db,query
        constraints()
        with db() as conn:
            conn.execute('UPDATE graph_outbox SET available_at=now()')
        while sync_batch(): pass
        me=self.login()
        rows=query("SELECT * FROM members WHERE status='approved' AND visible")
        scores=graph_candidates([str(p['id']) for p in rows],me)
        for p in rows:
            score=scores[str(p['id'])]
            self.assertEqual(score['help'],len(set(p['expertise']) & set(me['needs'])))
            self.assertEqual(score['mutual_help'],len(set(p['needs']) & set(me['expertise'])))
            from backend.taxonomy import occupation
            self.assertEqual(score['occupation'],int(occupation(p['occupation'])==occupation(me['occupation'])))
        result=driver.execute_query('''MATCH (p:Person {id:$id})-[:WORKS_AS]->(o:Occupation),
            (p)-[:LIVES_IN]->(:Zip)-[:IN_NEIGHBORHOOD]->(n:Neighborhood)
            RETURN p.name AS name,o.name AS occupation,n.name AS neighborhood,properties(p) AS props''',
            id=me['id'],database_='neo4j').records[0]
        self.assertEqual(result['name'],me['name'])
        self.assertEqual(result['occupation'],occupation(me['occupation']))
        self.assertEqual(result['neighborhood'],me['neighborhood'])
        self.assertNotIn('email',result['props'])
        self.assertNotIn('address',result['props'])
        needs=driver.execute_query('''MATCH (p:Person {id:$id})-[:NEEDS_HELP_WITH]->(n:Need:Expertise)
            RETURN n.name AS name''',id=me['id'],database_='neo4j').records
        self.assertEqual({r['name'] for r in needs},set(me['needs']))
        graph=self.client.get('/api/discover?radius=all').json()
        self.assertEqual(graph['engine'],'neo4j')
        with patch('backend.main.graph_candidates',side_effect=RuntimeError('offline')):
            fallback=self.client.get('/api/discover?radius=all').json()
        self.assertEqual(graph['profiles'],fallback['profiles'])
        location=self.client.get('/api/discover?radius=all&q=Jackson%20Heights').json()
        self.assertGreater(location['total'],0)

    def test_suspension_and_report(self):
        from backend.core import db
        me=self.login()
        email=uuid4().hex+'@example.com'
        with db() as conn:
            mid=str(conn.execute("INSERT INTO members(email,name,zip,occupation,languages,expertise,status,demo) VALUES(%s,'Moderation Test','11372','Tester',ARRAY['english'],ARRAY['testing'],'approved',true) RETURNING id",(email,)).fetchone()['id'])
        report=self.client.post('/api/reports',json={'memberId':mid,'reason':'A fictional moderation report'},headers=self.origin)
        self.assertEqual(report.status_code,200)
        self.assertEqual(self.client.post('/api/admin/members/'+mid,json={'status':'suspended'},headers=self.origin).status_code,200)
        self.assertEqual(self.client.get('/api/profiles/'+mid).status_code,404)
        self.assertEqual(self.client.post('/api/auth/demo',json={'email':email},headers=self.origin).status_code,404)
        self.assertEqual(self.client.post('/api/admin/reports/'+report.json()['id']+'/resolve',headers=self.origin).status_code,200)
        self.assertEqual(self.client.post('/api/admin/members/'+mid,json={'status':'approved'},headers=self.origin).status_code,200)

    def test_google_unapproved_account_and_state(self):
        from types import SimpleNamespace
        pending={'state':'test-state','nonce':'test-nonce','verifier':'verifier'}
        self.client.cookies.set('neighbor_oauth','fake-cookie')
        with patch('backend.auth.jwt.decode',return_value=pending):
            response=self.client.get('/api/auth/callback?state=wrong&code=code',follow_redirects=False)
            self.assertIn('could+not+be+verified',response.headers['location'])
        self.client.cookies.set('neighbor_oauth','fake-cookie')
        token_response=SimpleNamespace(raise_for_status=lambda:None,json=lambda:{'id_token':'token'})
        payload={'nonce':'test-nonce','email_verified':True,'email':'unapproved@example.com','sub':'google-sub'}
        with patch.dict(os.environ,{'GOOGLE_CLIENT_ID':'client','GOOGLE_CLIENT_SECRET':'secret'}), \
             patch('backend.auth.jwt.decode',side_effect=[pending,payload]), \
             patch('backend.auth.httpx.post',return_value=token_response), \
             patch('backend.auth.keys.get_signing_key_from_jwt',return_value=SimpleNamespace(key='key')):
            response=self.client.get('/api/auth/callback?state=test-state&code=code',follow_redirects=False)
            self.assertIn('needs+approval',response.headers['location'])


    def test_community_posts_events_and_privacy(self):
        from datetime import datetime, timezone, timedelta
        from backend.core import db
        author=self.login()
        payload={'kind':'need','title':'Find a realtor','body':'Looking for help selling a home.',
                 'tags':['real estate','technology'],'zip':'11372'}
        created=[]
        try:
            response=self.client.post('/api/posts',json=payload,headers=self.origin)
            self.assertEqual(response.status_code,200,response.text)
            pid=response.json()['id'];created.append(pid)
            event={**payload,'kind':'event','title':'Neighborhood clothing drive','venue':'Community center',
                   'starts_at':(datetime.now(timezone.utc)+timedelta(days=2)).isoformat()}
            response=self.client.post('/api/posts',json=event,headers=self.origin)
            self.assertEqual(response.status_code,200,response.text)
            eid=response.json()['id'];created.append(eid)
            self.assertEqual(self.client.post('/api/posts',json={**event,'starts_at':None},headers=self.origin).status_code,422)
            reader=self.login('arif@example.com')
            rows=self.client.get('/api/posts?radius=all').json()['posts']
            post=next(p for p in rows if p['id']==pid)
            self.assertNotIn('email',post);self.assertNotIn('lat',post)
            self.assertEqual(self.client.delete('/api/posts/'+pid,headers=self.origin).status_code,404)
            alerts=self.client.get('/api/notifications').json()['events']
            self.assertIn(eid,[p['id'] for p in alerts])
            self.assertEqual(self.client.post('/api/notifications/'+eid+'/read',headers=self.origin).status_code,200)
            self.assertNotIn(eid,[p['id'] for p in self.client.get('/api/notifications').json()['events']])
            with db() as conn:
                conn.execute('INSERT INTO blocks(blocker_id,blocked_id) VALUES(%s,%s) ON CONFLICT DO NOTHING',(reader['id'],author['id']))
            self.assertNotIn(pid,[p['id'] for p in self.client.get('/api/posts?radius=all').json()['posts']])
            with db() as conn:
                conn.execute('DELETE FROM blocks WHERE blocker_id=%s AND blocked_id=%s',(reader['id'],author['id']))
            self.login()
            self.assertEqual(self.client.delete('/api/posts/'+pid,headers=self.origin).status_code,200)
        finally:
            with db() as conn:
                for pid in created: conn.execute('DELETE FROM posts WHERE id=%s',(pid,))

    def test_optional_address_and_required_zip(self):
        self.login()
        data=self.submission()
        data['profile']['address']='123 Example Street'
        result=self.client.post('/api/admin/import',json={'submissions':[data]},headers=self.origin).json()
        sid=result['results'][0]['id']
        approved=self.client.post('/api/admin/submissions/'+sid,json={'approve':True},headers=self.origin)
        self.assertEqual(approved.status_code,200,approved.text)
        mid=approved.json()['memberId']
        from backend.core import db
        with db() as conn:
            self.assertEqual(conn.execute('SELECT address FROM members WHERE id=%s',(mid,)).fetchone()['address'],'123 Example Street')
        self.assertNotIn('address',self.client.get('/api/profiles/'+mid).json())
        profiles=self.client.get('/api/discover?radius=all').json()['profiles']
        self.assertTrue(all('address' not in p for p in profiles))
        original=self.client.get('/api/me').json()
        keys=['name','zip','occupation','workplace','bio','languages','cultures','countries','expertise','interests','needs','address']
        profile={k:original[k] for k in keys}
        try:
            self.assertEqual(self.client.patch('/api/me',json={**profile,'address':'456 Example Street'},headers=self.origin).status_code,200)
            self.assertEqual(self.client.get('/api/me').json()['address'],'456 Example Street')
            self.assertEqual(self.client.patch('/api/me',json={**profile,'zip':''},headers=self.origin).status_code,422)
            no_zip={k:v for k,v in profile.items() if k!='zip'}
            self.assertEqual(self.client.patch('/api/me',json=no_zip,headers=self.origin).status_code,422)
            no_address={k:v for k,v in profile.items() if k!='address'}
            self.assertEqual(self.client.patch('/api/me',json=no_address,headers=self.origin).status_code,200)
            self.assertEqual(self.client.get('/api/me').json()['address'],'')
        finally:
            self.client.patch('/api/me',json=profile,headers=self.origin)


    def test_message_pagination_retry_and_unread_boundary(self):
        from backend.core import db, one
        me=self.login()
        email=uuid4().hex+'@example.com'
        with db() as conn:
            target=conn.execute("INSERT INTO members(email,name,zip,status,demo) VALUES(%s,'Pagination Neighbor','11372','approved',true) RETURNING id",(email,)).fetchone()['id']
        cid=self.client.post('/api/conversations',json={'recipientId':str(target),'body':'First hello','clientMessageId':str(uuid4())},headers=self.origin).json()['id']
        self.login(email)
        self.client.post('/api/conversations/'+cid+'/decision',json={'action':'accept'},headers=self.origin)
        ids=[]
        for n in range(7):
            key=str(uuid4())
            payload={'body':'Message '+str(n),'clientMessageId':key}
            first=self.client.post('/api/conversations/'+cid+'/messages',json=payload,headers=self.origin)
            retry=self.client.post('/api/conversations/'+cid+'/messages',json=payload,headers=self.origin)
            self.assertEqual(first.status_code,200,first.text)
            self.assertEqual(first.json()['id'],retry.json()['id'])
            self.assertTrue(retry.json()['duplicate'])
            ids.append(first.json()['id'])
        conflict=self.client.post('/api/conversations/'+cid+'/messages',json={**payload,'body':'Changed'},headers=self.origin)
        self.assertEqual(conflict.status_code,409)
        page=self.client.get('/api/conversations/'+cid+'/messages?limit=3').json()
        self.assertEqual([m['id'] for m in page['messages']],ids[-3:])
        older=self.client.get('/api/conversations/'+cid+'/messages',params={'before':page['nextCursor'],'limit':3}).json()
        self.assertFalse(set(m['id'] for m in older['messages']) & set(ids[-3:]))
        delta=self.client.get('/api/conversations/'+cid+'/messages',params={'after':page['latestCursor']}).json()
        self.assertEqual(delta['messages'],[])
        self.assertEqual(self.client.get('/api/conversations?before=broken').status_code,400)
        self.login()
        self.client.post('/api/conversations/'+cid+'/read',json={'through':ids[3]},headers=self.origin)
        thread=next(t for t in self.client.get('/api/conversations').json()['conversations'] if t['id']==cid)
        self.assertEqual(thread['unread'],3)
        self.assertGreaterEqual(self.client.get('/api/inbox-summary').json()['unread'],3)

    def test_discovery_preferences_filters_and_modes(self):
        self.login()
        self.assertEqual(self.client.put('/api/preferences',json={'sharedCulture':True},headers=self.origin).status_code,200)
        self.assertTrue(self.client.get('/api/preferences').json()['sharedCulture'])
        for params in ['zip=11372','occupation=software+development','specialty=web+development','mode=help_me','mode=i_can_help','mode=shared','neighborhood=Jackson+Heights']:
            with patch('backend.main.graph_candidates',side_effect=RuntimeError('offline')):
                result=self.client.get('/api/discover?radius=all&'+params)
                self.assertEqual(result.status_code,200,result.text)
                for p in result.json()['profiles']:
                    if params.startswith('zip='): self.assertEqual(p['zip'],'11372')
                    if params.startswith('specialty='): self.assertIn('web development',p['expertise'])
        self.client.put('/api/preferences',json={'sharedCulture':False},headers=self.origin)
        self.assertFalse(self.client.get('/api/preferences').json()['sharedCulture'])

    def test_native_application_approval_preserves_authority(self):
        from backend.core import db,digest,one
        data=self.submission()
        cfg={'NATIVE_SIGNUP':'true','COGNITO_ISSUER':'https://issuer.example','COGNITO_DOMAIN':'https://login.example','COGNITO_CLIENT_ID':'test','SESSION_SECRET':'x'*40}
        with patch.dict(os.environ,cfg):
            with db() as conn:
                iid=conn.execute('INSERT INTO login_identities(issuer,subject,email) VALUES(%s,%s,%s) RETURNING id',('test',uuid4().hex,data['email'])).fetchone()['id']
                conn.execute("INSERT INTO applicant_sessions(token_hash,identity_id,expires_at) VALUES(%s,%s,now()+interval '1 hour')",(digest('applicant-token'),iid))
            self.client.cookies.set('neighbor_applicant','applicant-token')
            self.assertEqual(self.client.get('/api/application').json()['status'],'new')
            body={**data['profile'],'adult':True,'consent':True}
            self.assertEqual(self.client.post('/api/application',json=body,headers=self.origin).status_code,200)
            self.assertEqual(self.client.post('/api/application',json=body,headers=self.origin).json()['status'],'pending')
            self.assertEqual(self.client.get('/api/discover').status_code,401)
            self.assertEqual(self.client.get('/api/admin').status_code,401)
            self.login()
            sid=one('SELECT id FROM submissions WHERE identity_id=%s',(iid,))['id']
            response=self.client.post('/api/admin/submissions/'+str(sid),json={'approve':True},headers=self.origin)
            self.assertEqual(response.status_code,200,response.text)
            mid=response.json()['memberId']
            self.assertEqual(str(one('SELECT member_id FROM login_identities WHERE id=%s',(iid,))['member_id']),mid)
            self.assertEqual(one('SELECT role FROM members WHERE id=%s',(mid,))['role'],'member')
        with patch.dict(os.environ,{'NATIVE_SIGNUP':'false'}):
            self.assertEqual(self.client.get('/api/application').status_code,404)


    def test_managed_login_no_email_auto_link_and_replay(self):
        from types import SimpleNamespace
        import jwt
        from backend.core import one
        cfg={'NATIVE_SIGNUP':'true','COGNITO_ISSUER':'https://issuer.example','COGNITO_DOMAIN':'https://login.example','COGNITO_CLIENT_ID':'test','SESSION_SECRET':'x'*40}
        # Existing member authenticated in the app; first Cognito login MUST NOT auto-link by email.
        me=self.login()
        self.client.cookies.clear()
        subject='cognito-'+uuid4().hex
        def callback_for_start(link=False):
            start=self.client.post('/api/auth/cognito/link',headers=self.origin,follow_redirects=False) if link else self.client.get('/api/auth/cognito',follow_redirects=False)
            self.assertEqual(start.status_code,303,start.text)
            cookie=self.client.cookies.get('neighbor_cognito')
            pending=jwt.decode(cookie,cfg['SESSION_SECRET'],algorithms=['HS256'])
            claims={'nonce':pending['nonce'],'email_verified':True,'email':me['email'],'sub':subject,'token_use':'id'}
            token_response=SimpleNamespace(raise_for_status=lambda:None,json=lambda:{'id_token':'token'})
            with patch('backend.signup.jwt.decode',side_effect=[pending,claims]),patch('backend.signup.httpx.post',return_value=token_response),patch('backend.signup.jwt.PyJWKClient') as keys:
                keys.return_value.get_signing_key_from_jwt.return_value=SimpleNamespace(key='key')
                response=self.client.get('/api/auth/cognito/callback',params={'state':pending['state'],'code':'fake'},follow_redirects=False)
            return response,pending,cookie
        with patch.dict(os.environ,cfg):
            response,pending,cookie=callback_for_start()
            self.assertTrue(response.headers['location'].endswith('/signup'))
            self.assertIsNone(one('SELECT member_id FROM login_identities WHERE subject=%s',(subject,))['member_id'])
            self.assertEqual(self.client.get('/api/application').json()['status'],'link_required')
            self.assertEqual(self.client.get('/api/me').status_code,401)
            self.client.cookies.set('neighbor_cognito',cookie)
            with patch('backend.signup.httpx.post') as token_exchange:
                replay=self.client.get('/api/auth/cognito/callback',params={'state':pending['state'],'code':'fake'},follow_redirects=False)
                self.assertIn('status=expired',replay.headers['location'])
                token_exchange.assert_not_called()
            self.client.cookies.clear()
            self.login()
            response,_,_=callback_for_start(link=True)
            self.assertTrue(response.headers['location'].endswith('/discover'))
            linked=one('SELECT member_id FROM login_identities WHERE subject=%s',(subject,))
            self.assertEqual(str(linked['member_id']),me['id'])
            self.assertEqual(self.client.get('/api/me').json()['id'],me['id'])
            self.assertEqual(self.client.get('/api/me').json()['role'],me['role'])

    def test_concurrent_message_retry(self):
        from concurrent.futures import ThreadPoolExecutor
        from backend.core import db,one
        me=self.login()
        with db() as conn:
            target=conn.execute("INSERT INTO members(email,name,zip,status,demo) VALUES(%s,'Concurrent test','11372','approved',true) RETURNING id",(uuid4().hex+'@example.com',)).fetchone()['id']
            cid=conn.execute("INSERT INTO conversations(sender_id,recipient_id,status) VALUES(%s,%s,'accepted') RETURNING id",(me['id'],target)).fetchone()['id']
        payload={'body':'Send only once','clientMessageId':str(uuid4())}
        with ThreadPoolExecutor(max_workers=2) as workers:
            responses=list(workers.map(lambda _: self.client.post('/api/conversations/'+str(cid)+'/messages',json=payload,headers=self.origin),range(2)))
        self.assertEqual([r.status_code for r in responses],[200,200])
        self.assertEqual(responses[0].json()['id'],responses[1].json()['id'])
        self.assertEqual(one('SELECT count(*) AS n FROM messages WHERE conversation_id=%s',(cid,))['n'],1)

    def test_culture_opt_in_breaks_only_equal_matches(self):
        from backend.core import db
        me=self.login()
        with db() as conn:
            ids=[]
            for name,cultures in [('AAA culture test',[]),('ZZZ culture test',me['cultures'])]:
                ids.append(str(conn.execute("INSERT INTO members(email,name,zip,occupation,languages,expertise,interests,needs,cultures,status,demo) VALUES(%s,%s,%s,'Tester',ARRAY['english'],ARRAY['testing'],'{}','{}',%s,'approved',true) RETURNING id",(uuid4().hex+'@example.com',name,me['zip'],cultures)).fetchone()['id']))
        def ranked():
            return [p['id'] for p in self.client.get('/api/discover?radius=all&q=culture+test').json()['profiles']]
        self.client.put('/api/preferences',json={'sharedCulture':False},headers=self.origin)
        self.assertEqual(ranked(),ids)
        self.client.put('/api/preferences',json={'sharedCulture':True},headers=self.origin)
        self.assertEqual(ranked(),list(reversed(ids)))
        self.client.put('/api/preferences',json={'sharedCulture':False},headers=self.origin)


    def test_google_access_states_and_temporary_failure(self):
        from types import SimpleNamespace
        from urllib.parse import urlparse,parse_qs
        from backend.core import db
        from backend.intake import intake,review_submission
        from psycopg import OperationalError
        data=self.submission()
        pending_id=intake(data)['id']
        suspended=self.submission()
        sid=intake(suspended)['id']
        mid=review_submission(sid,True)['memberId']
        with db() as conn: conn.execute("UPDATE members SET status='suspended' WHERE id=%s",(mid,))
        pending={'state':'state','nonce':'nonce','verifier':'verifier'}
        res=SimpleNamespace(raise_for_status=lambda:None,json=lambda:{'id_token':'token'})
        for email,status in [(data['email'],'pending'),(suspended['email'],'suspended'),(uuid4().hex+'@example.com','wrong_account')]:
            self.client.cookies.set('neighbor_oauth','fake-cookie')
            payload={'nonce':'nonce','email_verified':True,'email':email,'sub':uuid4().hex}
            with patch.dict(os.environ,{'GOOGLE_CLIENT_ID':'client','GOOGLE_CLIENT_SECRET':'secret'}),patch('backend.auth.jwt.decode',side_effect=[pending,payload]),patch('backend.auth.httpx.post',return_value=res),patch('backend.auth.keys.get_signing_key_from_jwt',return_value=SimpleNamespace(key='key')):
                response=self.client.get('/api/auth/callback?state=state&code=fake',follow_redirects=False)
                self.assertEqual(parse_qs(urlparse(response.headers['location']).query)['status'],[status])
        self.client.cookies.set('neighbor_oauth','fake-cookie')
        with patch.dict(os.environ,{'GOOGLE_CLIENT_ID':'client','GOOGLE_CLIENT_SECRET':'secret'}),patch('backend.auth.jwt.decode',side_effect=[pending,payload]),patch('backend.auth.httpx.post',return_value=res),patch('backend.auth.keys.get_signing_key_from_jwt',return_value=SimpleNamespace(key='key')),patch('backend.auth.db',side_effect=OperationalError('private database diagnostic')):
            with self.assertLogs('backend.auth',level='WARNING') as logs:
                response=self.client.get('/api/auth/callback?state=state&code=fake',follow_redirects=False)
            self.assertEqual(parse_qs(urlparse(response.headers['location']).query)['status'],['temporary'])
            self.assertNotIn('private database diagnostic',' '.join(logs.output))

if __name__=='__main__': unittest.main()
