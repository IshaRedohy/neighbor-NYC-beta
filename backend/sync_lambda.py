import os
from .runtime import load_secrets
load_secrets()
from .core import db_open, db, one
from .graph import constraints, sync_batch

db_open()

def handler(event, context):
    try:
        with db() as conn:
            conn.execute('DELETE FROM sessions WHERE expires_at<now()')
            conn.execute('DELETE FROM applicant_sessions WHERE expires_at<now()')
            conn.execute('DELETE FROM oauth_attempts WHERE expires_at<now()')
            conn.execute("DELETE FROM rate_limits WHERE window_start<now()-interval '1 day'")
        if os.getenv('GRAPH_ENABLED','true') != 'true':
            return {'batchItemFailures': []}
        constraints()
        # One bounded job. More work is retried by SQS or recovered by the hourly schedule.
        budget = min(80, max(1, context.get_remaining_time_in_millis()/1000-20))
        sync_batch(limit=50, budget_seconds=budget)
        remaining = one('SELECT 1 FROM graph_outbox LIMIT 1')
        if remaining:
            raise RuntimeError('OutboxPending')
    except Exception:
        records = event.get('Records', [])
        if records:
            return {'batchItemFailures':[{'itemIdentifier':r['messageId']} for r in records]}
        # EventBridge retries and sends exhausted failures to its own DLQ.
        raise RuntimeError('GraphSyncIncomplete') from None
    return {'batchItemFailures': []}
