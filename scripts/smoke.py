"""Exercise the actual Next.js -> FastAPI proxy with fictional demo sessions.

No production use: requires a local demo config. Creates no member data.
"""
import httpx

with httpx.Client(base_url='http://localhost:3000',timeout=25,headers={'Origin':'http://localhost:3000'}) as client:
    config=client.get('/api/config').json()
    assert config['demo'], 'Smoke check only runs with demo mode enabled.'
    assert client.get('/').status_code==200
    assert client.get('/api/discover').status_code==401
    login=client.post('/api/auth/demo',json={'email':'maya@example.com'})
    assert login.status_code==200,login.text
    assert 'HttpOnly' in login.headers.get('set-cookie','')
    me=client.get('/api/me').json()
    assert me['name']=='Maya Rahman'
    discovery=client.get('/api/discover',params={'radius':'all'}).json()
    assert discovery['total']>=11,discovery
    assert discovery['engine']=='neo4j',discovery['engine']
    assert all('email' not in p for p in discovery['profiles'])
    for path in ['/discover','/messages','/profile','/admin']:
        assert client.get(path).status_code==200,path
    assert client.get('/api/admin').status_code==200
    assert client.post('/api/auth/logout').status_code==200
    assert client.get('/api/me').status_code==401
    assert client.post('/api/auth/demo',json={'email':'arif@example.com'}).status_code==200
    assert client.get('/api/admin').status_code==403
    assert client.post('/api/auth/logout').status_code==200
    print('PASS: page delivery, proxied sessions, Neo4j discovery, private emails, admin boundary, and logout.')
