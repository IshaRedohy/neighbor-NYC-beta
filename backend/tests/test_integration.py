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
        migrate()
        seed()
        from backend.core import db
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
        self.assertTrue(next(t for t in self.client.get('/api/conversations').json() if t['id']==cid)['unread']>0)
        self.assertEqual(self.client.post('/api/conversations/'+cid+'/decision',json={'action':'accept'},headers=self.origin).status_code,200)
        self.assertEqual(self.client.post('/api/conversations/'+cid+'/messages',json={'body':'Happy to help'},headers=self.origin).status_code,200)
        self.client.post('/api/conversations/'+cid+'/read',headers=self.origin)
        self.assertEqual(next(t for t in self.client.get('/api/conversations').json() if t['id']==cid)['unread'],0)
        self.client.post('/api/blocks/'+maya['id'],headers=self.origin)
        self.assertEqual(self.client.get('/api/profiles/'+maya['id']).status_code,404)
        self.assertEqual(self.client.post('/api/conversations/'+cid+'/messages',json={'body':'Blocked'},headers=self.origin).status_code,403)
        self.login()
        self.assertEqual(self.client.get('/api/profiles/'+str(target['id'])).status_code,404)
        self.assertFalse(any(t['id']==cid for t in self.client.get('/api/conversations').json()))

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

if __name__=='__main__': unittest.main()
