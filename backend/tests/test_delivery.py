import os
import unittest
from unittest.mock import patch, MagicMock

class DeliveryTests(unittest.TestCase):
    def test_failed_notification_does_not_fail_committed_write(self):
        from backend.sync_delivery import notify_sync
        with patch.dict(os.environ,{'GRAPH_QUEUE_URL':'https://sqs.example/queue','GRAPH_ENABLED':'true'}),patch('backend.sync_delivery.sqs') as client:
            client.return_value.send_message.side_effect=RuntimeError('do not log private details')
            with self.assertLogs('backend.sync_delivery',level='WARNING') as logs:
                notify_sync()
            self.assertNotIn('private details',' '.join(logs.output))

    def test_disabled_graph_does_not_call_queue(self):
        from backend.sync_delivery import notify_sync
        with patch.dict(os.environ,{'GRAPH_QUEUE_URL':'queue','GRAPH_ENABLED':'false'}),patch('backend.sync_delivery.sqs') as client:
            notify_sync()
            client.assert_not_called()

    def test_invalid_production_database_tls_is_rejected(self):
        from backend.runtime import load_secrets
        with patch.dict(os.environ,{'APP_SECRET_ARN':'','ENVIRONMENT':'production','DEMO_MODE':'false','APP_URL':'https://example.test','DATABASE_URL':'postgresql://localhost/db'}):
            with self.assertRaisesRegex(RuntimeError,'TLS'): load_secrets()

    def test_bounded_worker_partial_failure_and_scheduled_recovery(self):
        import importlib
        with patch('backend.runtime.load_secrets'),patch('backend.core.db_open'):
            worker=importlib.import_module('backend.sync_lambda')
        context=MagicMock()
        context.get_remaining_time_in_millis.return_value=120000
        with patch.dict(os.environ,{'GRAPH_ENABLED':'true'}),patch.object(worker,'constraints'),patch.object(worker,'sync_batch') as sync,patch.object(worker,'db'),patch.object(worker,'one',return_value={'pending':1}):
            result=worker.handler({'Records':[{'messageId':'test-notification'}]},context)
            self.assertEqual(result,{'batchItemFailures':[{'itemIdentifier':'test-notification'}]})
            self.assertLessEqual(sync.call_args.kwargs['budget_seconds'],80)
            with self.assertRaisesRegex(RuntimeError,'GraphSyncIncomplete'):
                worker.handler({},context)
        with patch.dict(os.environ,{'GRAPH_ENABLED':'true'}),patch.object(worker,'constraints'),patch.object(worker,'sync_batch'),patch.object(worker,'db'),patch.object(worker,'one',return_value=None):
            self.assertEqual(worker.handler({},context),{'batchItemFailures':[]})
