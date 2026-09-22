"""Offline checks: saved tokens must avoid password login, including after 429."""

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import requests

from scripts.garmin.garmin_client import GarminClient
from scripts import garmin_token


class GarminAuthTests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ, {}, clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        factory = patch("scripts.garmin.garmin_client.garth.Client")
        self.factory = factory.start()
        self.addCleanup(factory.stop)
        self.client = self.factory.return_value
        self.client.oauth1_token = object()
        self.client.oauth2_token = SimpleNamespace(expired=False)

    def test_action_loads_secret_and_never_relogs_on_api_error(self):
        os.environ.update(GITHUB_ACTIONS="true", GARMIN_TOKEN="saved-token")
        garmin = GarminClient("", "", "COM", 0)
        self.client.loads.assert_called_once_with("saved-token")
        self.client.connectapi.side_effect = requests.HTTPError("429 Too Many Requests")
        with self.assertRaises(requests.HTTPError):
            garmin.getActivities(0, 100)
        self.client.login.assert_not_called()
        self.client.refresh_oauth2.assert_not_called()

    def test_expired_token_refreshes_before_direct_upload(self):
        garmin = GarminClient("", "", "COM", 0)
        self.client.domain = "garmin.com"
        self.client.oauth2_token = SimpleNamespace(expired=True)
        self.client.refresh_oauth2.side_effect = lambda: setattr(self.client, "oauth2_token", "fresh-token")
        with tempfile.TemporaryDirectory() as directory:
            activity = Path(directory) / "activity.fit"
            activity.write_bytes(b"test")
            with patch("scripts.garmin.garmin_client.requests.post") as post:
                post.return_value.status_code = 202
                post.return_value.json.return_value = {"detailedImportResult": {"uploadId": "123"}}
                self.assertEqual(garmin.upload_activity(str(activity)), "SUCCESS")
                self.assertEqual(post.call_args.kwargs["headers"]["Authorization"], "fresh-token")
        self.client.refresh_oauth2.assert_called_once()
        self.client.login.assert_not_called()

    def test_action_without_token_fails_before_login(self):
        os.environ["GITHUB_ACTIONS"] = "true"
        with self.assertRaisesRegex(RuntimeError, "GARMIN_TOKEN"):
            GarminClient("email", "password", "COM", 0)
        self.client.login.assert_not_called()

    def test_invalid_secret_is_not_printed_or_replaced_by_password_login(self):
        os.environ["GARMIN_TOKEN"] = "invalid-secret"
        self.client.loads.side_effect = ValueError("invalid-secret")
        with self.assertRaises(ValueError) as error:
            GarminClient("email", "password", "COM", 0)
        self.assertNotIn("invalid-secret", str(error.exception))
        self.client.login.assert_not_called()

    def test_local_password_login_is_preserved(self):
        self.client.oauth1_token = None
        garmin = GarminClient("email", "password", "CN", 0)
        garmin.downloadFitActivity(123)
        self.factory.assert_called_once_with(domain="garmin.cn")
        self.client.login.assert_called_once_with("email", "password")
        self.client.download.assert_called_once()

    def test_export_existing_session_without_printing_token(self):
        self.client.dumps.return_value = "encoded-token"
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(garmin_token, "__file__", str(Path(directory) / "scripts" / "garmin_token.py")):
                with patch("sys.argv", ["garmin_token.py", "--session-dir", "saved-session"]):
                    with patch("builtins.print") as output:
                        garmin_token.main()
            self.assertEqual((Path(directory) / ".garmin-token").read_text(), "encoded-token")
            self.assertNotIn("encoded-token", str(output.call_args))
        self.client.load.assert_called_once_with("saved-session")
        self.client.login.assert_not_called()

    def test_credentials_file_check_only_preserves_password_and_skips_export(self):
        with tempfile.TemporaryDirectory() as directory:
            credentials = Path(directory) / "credentials.ini"
            credentials.write_text(
                "[sync]\nGARMIN_EMAIL = runner@example.com\nGARMIN_PASSWORD = p%a#s;s=word\n"
                "GARMIN_AUTH_DOMAIN = CN\nGARMIN_NEWEST_NUM = 0\nCOROS_EMAIL =\nCOROS_PASSWORD =\n",
                encoding="utf-8-sig",
            )
            with patch("sys.argv", ["garmin_token.py", "--credentials", str(credentials), "--check-only"]):
                with patch("builtins.input", side_effect=AssertionError("Unexpected prompt")):
                    with patch("builtins.print") as output:
                        garmin_token.main()
            self.factory.assert_called_once_with(domain="garmin.cn")
            self.client.login.assert_called_once_with("runner@example.com", "p%a#s;s=word")
            self.client.dumps.assert_not_called()
            self.assertNotIn("p%a#s;s=word", str(output.call_args))
            credentials.write_text("[sync]\nGARMIN_EMAIL = runner@example.com\nGARMIN_PASSWORD =\nGARMIN_AUTH_DOMAIN = COM\n")
            self.client.login.reset_mock()
            with patch("sys.argv", ["garmin_token.py", "--credentials", str(credentials), "--check-only"]):
                with self.assertRaises(ValueError):
                    garmin_token.main()
            self.client.login.assert_not_called()


if __name__ == "__main__":
    unittest.main()
