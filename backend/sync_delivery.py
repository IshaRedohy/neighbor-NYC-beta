"""Best-effort queue wake-up. The transactional SQL outbox remains authoritative."""
import logging
import os
from functools import lru_cache

@lru_cache(maxsize=1)
def sqs():
    import boto3
    from botocore.config import Config
    return boto3.client('sqs', config=Config(connect_timeout=2, read_timeout=2, retries={'max_attempts':1}))

def notify_sync():
    url = os.getenv('GRAPH_QUEUE_URL')
    if not url or os.getenv('GRAPH_ENABLED','true') != 'true':
        return
    try:
        # No member identifiers or profile content in queue payloads.
        sqs().send_message(QueueUrl=url, MessageBody='{"action":"sync"}')
    except Exception as exc:
        logging.getLogger(__name__).warning('Graph notification deferred: exception=%s', type(exc).__name__)
