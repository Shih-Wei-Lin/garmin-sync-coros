import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from cryptography.fernet import Fernet

from scripts.garmin.garmin_client import GarminClient, GarminNoLoginException
from scripts.garmin_session_cache import transfer_session


class GarminAuthTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'GARMINTOKENS': '/test/session'})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.factory = patch('scripts.garmin.garmin_client.Garmin')
        self.api = self.factory.start().return_value
        self.addCleanup(self.factory.stop)

    def test_resume_once_and_delegate_download(self):
        client = GarminClient('email', 'password', 'COM', 0)
        client.getActivities(0, 1)
        self.assertIs(client.downloadFitActivity(123), self.api.download.return_value)
        self.api.login.assert_called_once_with('/test/session')
        self.api.client.dump.assert_called_once_with('/test/session')
        self.api.connectapi.assert_called_once_with(
            '/activitylist-service/activities/search/activities',
            params={'start': '0', 'limit': '1'},
        )

    def test_china_region(self):
        with patch('scripts.garmin.garmin_client.Garmin') as factory:
            GarminClient('email', 'password', 'cn', 0)
        factory.assert_called_once_with('email', 'password', is_cn=True)

    def test_invalid_region(self):
        with self.assertRaises(ValueError):
            GarminClient('email', 'password', 'invalid', 0)

    def test_login_failure_hides_secrets_and_does_not_call_api(self):
        self.api.login.side_effect = RuntimeError('private password and token')
        client = GarminClient('email', 'password', 'COM', 0)
        with self.assertRaises(GarminNoLoginException) as error:
            client.getActivities(0, 1)
        self.assertNotIn('private', str(error.exception))
        self.api.connectapi.assert_not_called()
        self.api.login.assert_called_once()

    def test_upload_preserves_success_duplicate_and_other_failures(self):
        duplicate = {'failures': [{'messages': [{'content': 'Duplicate Activity.'}]}]}
        cases = [(202, {'uploadId': 42}, 'SUCCESS'),
                 (409, duplicate, 'DUPLICATE_ACTIVITY'),
                 (409, {'failures': []}, 'UPLOAD_EXCEPTION'),
                 (202, {}, 'UPLOAD_EXCEPTION')]
        self.api.client.domain = 'garmin.com'
        self.api.client.get_api_headers.return_value = {'Authorization': 'Bearer fake'}
        with tempfile.TemporaryDirectory() as folder:
            activity = Path(folder) / 'activity.fit'
            activity.write_bytes(b'fit')
            for code, detail, expected in cases:
                with self.subTest(code=code, expected=expected), patch(
                    'scripts.garmin.garmin_client.requests.post'
                ) as post:
                    post.return_value = Mock(status_code=code)
                    post.return_value.json.return_value = {'detailedImportResult': detail}
                    client = GarminClient('email', 'password', 'COM', 0)
                    self.assertEqual(client.upload_activity(str(activity)), expected)
                    self.assertEqual(post.call_args.kwargs['timeout'], 60)
                    self.assertEqual(post.call_args.kwargs['headers']['Authorization'], 'Bearer fake')
                    self.api.connectapi.assert_called_with('/userprofile-service/socialProfile')


class SessionCacheTests(unittest.TestCase):
    def test_encrypted_round_trip_and_wrong_key(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            tokenstore = root / 'tokens'
            tokenstore.mkdir()
            token = tokenstore / 'garmin_tokens.json'
            payload = b'{"di_refresh_token": "private-refresh-token"}'
            token.write_bytes(payload)
            cache = root / 'cache' / 'session.enc'
            key = Fernet.generate_key()
            transfer_session('save', tokenstore, cache, key)
            self.assertNotIn(b'private-refresh-token', cache.read_bytes())
            token.unlink()
            with self.assertRaises(RuntimeError):
                transfer_session('restore', tokenstore, cache, Fernet.generate_key())
            self.assertFalse(token.exists())
            transfer_session('restore', tokenstore, cache, key)
            self.assertEqual(token.read_bytes(), payload)

    def test_missing_cache_or_session_is_ok(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            key = Fernet.generate_key()
            transfer_session('restore', root / 'tokens', root / 'session.enc', key)
            transfer_session('save', root / 'tokens', root / 'session.enc', key)
            self.assertFalse((root / 'session.enc').exists())


if __name__ == '__main__':
    unittest.main()
