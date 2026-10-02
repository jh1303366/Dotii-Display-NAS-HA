import os
from pathlib import Path
import queue
import sys
import time
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from codex_app_server import AppServerError, CodexAppServerSource, account_snapshot, thread_snapshot
from codex_auth import CodexAuthService

class NasQuotaTests(unittest.TestCase):
    def test_named_codex_bucket_wins_over_legacy_other_bucket(self):
        snapshot = account_snapshot({
            'rateLimits': {'limitId': 'other', 'primary': {'windowDurationMins': 10080, 'usedPercent': 0}},
            'rateLimitsByLimitId': {'codex': {'planType': 'pro', 'primary': {'windowDurationMins': 10080, 'usedPercent': 82}}},
        }, {})
        self.assertEqual(snapshot['weekly_remaining_percent'], 18)
        self.assertEqual(snapshot['plan_type'], 'pro')

    def test_other_bucket_does_not_fill_a_missing_codex_window(self):
        snapshot = account_snapshot({'rateLimitsByLimitId': {
            'codex': {'primary': {'windowDurationMins': 10080, 'usedPercent': 20}},
            'other': {'primary': {'windowDurationMins': 300, 'usedPercent': 5}},
        }}, {})
        self.assertFalse(snapshot['five_hour_available'])
        self.assertEqual(snapshot['weekly_remaining_percent'], 80)

    def test_invalid_percentage_does_not_break_snapshot(self):
        result = account_snapshot({'rateLimits': {'primary': {'windowDurationMins': 300, 'usedPercent': float('nan')}}}, {})
        self.assertFalse(result['five_hour_available'])

    @staticmethod
    def source():
        source = CodexAppServerSource.__new__(CodexAppServerSource)
        source.account = account_snapshot({}, {})
        source.task = thread_snapshot(None)
        source.tasks = [source.task]
        source._has_account_snapshot = True
        source._account_refresh_failures = 0
        source.last_account_refresh = 0
        source.client = mock.Mock()
        return source

    def test_optional_usage_failure_keeps_real_quota(self):
        source = self.source()
        def respond(method):
            if method == 'account/rateLimits/read':
                return {'rateLimits': {'primary': {'windowDurationMins': 300, 'usedPercent': 42}}}
            raise AppServerError('method not supported')
        source.client.request.side_effect = respond
        source.refresh_account(force=True)
        self.assertEqual(source.account['five_hour_remaining_percent'], 58)
        self.assertFalse(source.account['weekly_tokens_available'])
        self.assertGreater(source.account['account_updated_at_epoch'], 0)

    def test_quota_only_avoids_thread_calls_and_keeps_real_update_time(self):
        source = self.source()
        source.account.update(account_updated_at_epoch=123)
        source.refresh_account = mock.Mock()
        source.refresh_thread = mock.Mock(side_effect=AssertionError('must not read desktop tasks'))
        with mock.patch.dict(os.environ, {'DOTII_CODEX_QUOTA_ONLY': '1'}):
            snapshot = source.snapshot()
        source.refresh_thread.assert_not_called()
        self.assertEqual(snapshot['generated_at_epoch'], 123)

    def test_failed_refresh_marks_cached_data_stale_without_resetting_time(self):
        source = self.source()
        source.account.update(account_updated_at_epoch=123, account_stale=False)
        source.refresh_account = mock.Mock(side_effect=AppServerError('network disconnected'))
        with mock.patch.dict(os.environ, {'DOTII_CODEX_QUOTA_ONLY': '1'}):
            snapshot = source.snapshot()
        self.assertTrue(snapshot['codex']['account_stale'])
        self.assertEqual(snapshot['generated_at_epoch'], 123)

class NasLoginTests(unittest.TestCase):
    def service(self):
        callback = mock.Mock()
        return CodexAuthService(Path('/data'), Path('/app'), None, callback), callback

    def test_device_login_publishes_code_then_clears_it_on_success(self):
        service, callback = self.service()
        with mock.patch('codex_auth._resolve_codex_command', return_value=['codex']), mock.patch('codex_auth.AppServerClient') as factory:
            client = factory.return_value
            client.request.return_value = {'loginId': 'test-login', 'verificationUrl': 'https://auth.openai.com/codex/device', 'userCode': 'ABCD-1234'}
            def completion(timeout):
                self.assertEqual(service.snapshot()['user_code'], 'ABCD-1234')
                return {'method': 'account/login/completed', 'params': {'loginId': 'test-login', 'success': True}}
            client.notifications.get.side_effect = completion
            service._run(True)
        self.assertEqual(service.snapshot()['state'], 'logged_in')
        self.assertEqual(service.snapshot()['user_code'], '')
        callback.assert_called_once()
        client.close.assert_called_once()

    def test_untrusted_login_link_is_rejected(self):
        service, callback = self.service()
        with mock.patch('codex_auth._resolve_codex_command', return_value=['codex']), mock.patch('codex_auth.AppServerClient') as factory:
            factory.return_value.request.return_value = {'verificationUrl': 'https://attacker.invalid', 'userCode': 'CODE'}
            service._run(True)
        self.assertEqual(service.snapshot()['state'], 'error')
        self.assertEqual(service.snapshot()['verification_url'], '')
        callback.assert_not_called()

    def test_login_errors_do_not_expose_token_details(self):
        service, callback = self.service()
        with mock.patch('codex_auth._resolve_codex_command', side_effect=AppServerError('secret-access-token')):
            service._run(True)
        self.assertNotIn('secret-access-token', str(service.snapshot()))

    def test_saved_login_can_be_detected_after_restart(self):
        service, callback = self.service()
        with mock.patch('codex_auth._resolve_codex_command', return_value=['codex']), mock.patch('codex_auth.AppServerClient') as factory:
            factory.return_value.request.return_value = {'account': {'type': 'chatgpt'}}
            service._run(False)
        self.assertEqual(service.snapshot()['state'], 'logged_in')
