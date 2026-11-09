"""Daily encrypted logical backup via pg_dump in the Lambda container image."""
import os
import subprocess
import tempfile
from datetime import datetime, timezone
import boto3
from .runtime import load_secrets

def handler(event, context):
    load_secrets()
    url = os.environ['DIRECT_DATABASE_URL']
    # Pass credentials through process env, never command arguments or error logs.
    with tempfile.TemporaryDirectory() as directory:
        target = directory+'/database.dump'
        result = subprocess.run(['pg_dump','--format=custom','--no-owner','--no-acl','--file',target],
                                env={**os.environ,'PGDATABASE':url}, capture_output=True, timeout=240)
        if result.returncode:
            raise RuntimeError('DatabaseBackupFailed')
        key = datetime.now(timezone.utc).strftime('%Y/%m/%d/%H%M%S.dump')
        boto3.client('s3').upload_file(target, os.environ['BACKUP_BUCKET'], key,
            ExtraArgs={'ServerSideEncryption':'AES256'})
    return {'ok':True}
