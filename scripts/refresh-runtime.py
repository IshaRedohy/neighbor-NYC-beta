"""Recycle warm Lambda clients after updating a Secrets Manager configuration."""
import json
import time
from pathlib import Path
import boto3
client=boto3.client('lambda',region_name='us-east-1')
outputs=json.loads(Path('.artifacts/outputs.json').read_text())
for stack in outputs.values():
    for key in ('ApiFunction','GraphFunction','BackupFunction'):
        name=stack[key]
        config=client.get_function_configuration(FunctionName=name)
        environment=config['Environment']['Variables']
        environment['CONFIG_REVISION']=str(time.time_ns())
        client.update_function_configuration(FunctionName=name,Environment={'Variables':environment})
        client.get_waiter('function_updated_v2').wait(FunctionName=name)
print('Runtime configuration refreshed.')
