import json
import os
import sys
import subprocess
from pathlib import Path
import boto3
import httpx

if sys.argv[1]=='migrate':
    secret=json.loads(boto3.client('secretsmanager').get_secret_value(SecretId=os.environ['APP_SECRET_ARN'])['SecretString'])
    env={**os.environ,**secret,'DATABASE_URL':secret['DIRECT_DATABASE_URL'],'ENVIRONMENT':'production','DEMO_MODE':'false'}
    subprocess.run([sys.executable,'-m','backend.cli','migrate'],env=env,check=True)
    Path('.artifacts').mkdir(exist_ok=True)
else:
    outputs=json.loads(Path('.artifacts/outputs.json').read_text())['Neighbor-'+os.environ['STAGE']]
    # Retain old hashed assets so existing tabs and rollback releases still work.
    subprocess.run(['aws','s3','sync','out/', 's3://'+outputs['SiteBucket']+'/', '--cache-control','public,max-age=0,must-revalidate'],check=True)
    result=boto3.client('cloudfront').create_invalidation(DistributionId=outputs['DistributionId'],InvalidationBatch={
        'Paths':{'Quantity':1,'Items':['/*']},'CallerReference':str(__import__('time').time_ns())})
    boto3.client('cloudfront').get_waiter('invalidation_completed').wait(DistributionId=outputs['DistributionId'],Id=result['Invalidation']['Id'])
    with httpx.Client(base_url=outputs['AppUrl'],timeout=30) as client:
        assert client.get('/api/health').status_code==200
        assert client.get('/api/me').status_code==401
        assert client.get('/api/admin').status_code==401
        for route in ['/','/discover','/community','/messages','/profile','/admin']:
            assert client.get(route).status_code==200,route
    print('Deployed and smoke-tested:',outputs['AppUrl'])
