"""Safe configuration/migration helper: secrets never enter command arguments or output."""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dotenv import dotenv_values
import boto3

parser=argparse.ArgumentParser()
parser.add_argument('action',choices=['secret','migrate','bootstrap'])
parser.add_argument('--env-file',required=True)
parser.add_argument('--secret-name')
parser.add_argument('--email')
args=parser.parse_args()
values={k:v for k,v in dotenv_values(args.env_file).items() if v}
if args.action=='secret':
    required=['DATABASE_URL','DIRECT_DATABASE_URL','SESSION_SECRET','INTAKE_SECRET','APP_URL','GOOGLE_CLIENT_ID','GOOGLE_CLIENT_SECRET']
    if any(not values.get(k) for k in required):
        raise SystemExit('Fill all required settings in the local environment file first.')
    if not args.secret_name: parser.error('--secret-name is required')
    client=boto3.client('secretsmanager',region_name='us-east-1')
    try:
        result=client.create_secret(Name=args.secret_name,SecretString=json.dumps(values))
    except client.exceptions.ResourceExistsException:
        result=client.put_secret_value(SecretId=args.secret_name,SecretString=json.dumps(values))
    print('Configuration saved:',result['ARN'])
else:
    if not values.get('DIRECT_DATABASE_URL'): raise SystemExit('DIRECT_DATABASE_URL is required.')
    env={**os.environ,**values,'DATABASE_URL':values['DIRECT_DATABASE_URL'],'ENVIRONMENT':'production','DEMO_MODE':'false'}
    command=[sys.executable,'-m','backend.cli','migrate']
    if args.action=='bootstrap':
        if not args.email: parser.error('--email is required for bootstrap')
        command=[sys.executable,'-m','backend.cli','bootstrap-admin','--email',args.email]
    result=subprocess.run(command,env=env)
    raise SystemExit(result.returncode)
