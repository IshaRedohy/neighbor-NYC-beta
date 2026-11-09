"""Run inside the Linux Lambda image with dummy production configuration; no database access."""
import json
from types import SimpleNamespace
from backend.lambda_handler import handler
from backend.core import pool
for path,method,status in [('/api/config','GET',200),('/api/me','GET',401),('/api/admin','GET',401),('/api/auth/demo','POST',404)]:
    event={'version':'2.0','routeKey':'$default','rawPath':path,'rawQueryString':'',
           'headers':{'host':'example.test','origin':'https://example.test','content-type':'application/json'},
           'requestContext':{'http':{'method':method,'path':path,'protocol':'HTTP/1.1','sourceIp':'127.0.0.1','userAgent':'smoke'},'stage':'$default'},
           'body':'{}' if method=='POST' else '', 'isBase64Encoded':False}
    result=handler(event,SimpleNamespace(aws_request_id='smoke'))
    assert result['statusCode']==status,(path,result['statusCode'])
    if path=='/api/config': assert json.loads(result['body'])['demo'] is False
    assert result['headers']['cache-control']=='no-store'
pool.close()
print('Linux Lambda production adapter smoke checks passed.')
