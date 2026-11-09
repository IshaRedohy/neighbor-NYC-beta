"""Resolve production secrets before importing modules that construct clients."""
import json
import os

ALLOWED = {'APP_URL','COGNITO_ISSUER','COGNITO_DOMAIN','COGNITO_CLIENT_ID','NATIVE_SIGNUP','DATABASE_URL','DIRECT_DATABASE_URL','NEO4J_URI','NEO4J_USER','NEO4J_PASSWORD',
           'GOOGLE_CLIENT_ID','GOOGLE_CLIENT_SECRET','GOOGLE_FORM_ID','INTAKE_SECRET','SESSION_SECRET'}

def load_secrets():
    if os.getenv('APP_SECRET_ARN'):
        import boto3
        result = boto3.client('secretsmanager').get_secret_value(SecretId=os.environ['APP_SECRET_ARN'])
        values = json.loads(result['SecretString'])
        for key in ALLOWED:
            if key in values:
                os.environ[key] = str(values[key])
    if os.getenv('ENVIRONMENT') != 'production' or os.getenv('DEMO_MODE') != 'false':
        raise RuntimeError('Lambda requires production configuration and demo access disabled.')
    if not os.getenv('APP_URL','').startswith('https://'):
        raise RuntimeError('Production APP_URL must use HTTPS.')
    from urllib.parse import urlparse, parse_qs
    url = urlparse(os.getenv('DATABASE_URL',''))
    if parse_qs(url.query).get('sslmode', [''])[0] not in ('require','verify-full'):
        raise RuntimeError('Production PostgreSQL requires TLS.')
    if len(os.getenv('SESSION_SECRET','')) < 32 or len(os.getenv('INTAKE_SECRET','')) < 32:
        raise RuntimeError('Production secrets are missing.')
