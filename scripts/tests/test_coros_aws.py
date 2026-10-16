import json
import runpy
import sys
import unittest
from contextlib import ExitStack, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from oss.aws_oss_client import AwsOssClient
from oss.sts_token_error import StsTokenError
from coros.coros_client import CorosClient, CorosActivityUploadError


class CorosAwsTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.http = self.stack.enter_context(patch('oss.aws_oss_client.urllib3.PoolManager')).return_value
        self.boto = self.stack.enter_context(patch('oss.aws_oss_client.boto3.client'))
        self.decode = self.stack.enter_context(patch('oss.aws_oss_client.decode'))
        self.http.request.return_value = Mock(
            status=200, data=json.dumps({'code': 200, 'data': {'credentials': 'encoded'}}).encode()
        )
        self.decode.return_value = {
            'AccessKeyId': 'fake-id', 'SecretAccessKey': 'fake-secret',
            'SessionToken': 'fake-session', 'Region': 'us-west-2', 'Bucket': 'coros-s3',
        }

    def test_region_host_bucket_and_session_cookie(self):
        for region_id, host, bucket, aws_region in [
            (1, 'training.coros.com', 'coros-s3', 'us-west-2'),
            (3, 'trainingeu.coros.com', 'eu-coros', 'eu-central-1'),
        ]:
            with self.subTest(region_id=region_id):
                self.decode.return_value.update(Bucket=bucket, Region=aws_region)
                client = AwsOssClient('private-token', region_id)
                self.http.request.assert_called_with(
                    'GET', f'https://{host}/api/proxy/oss/sts?bucket={bucket}&service=aws&v=2',
                    headers={'Cookie': 'CPL-coros-token=private-token'},
                    timeout=20, retries=False, redirect=False,
                )
                self.assertEqual(client.bucket, bucket)
                self.assertEqual(self.boto.call_args.kwargs['region_name'], aws_region)

    def test_non_json_and_rejected_responses_fail_without_leaking_content(self):
        for status, body in [(404, b'<html>private response</html>'),
                             (200, b'<html>private response</html>'),
                             (200, b'{"code":401,"message":"private response"}'),
                             (200, b'[]')]:
            with self.subTest(status=status, body=body):
                self.http.request.return_value = Mock(status=status, data=body)
                with self.assertRaises(StsTokenError) as error:
                    AwsOssClient('private-token', 1)
                self.assertNotIn('private', str(error.exception))
        self.boto.assert_not_called()

    def test_invalid_credentials_and_bucket_are_rejected(self):
        for credentials in [{}, {'Bucket': 'other-bucket'},
                            {**self.decode.return_value, 'Bucket': 'eu-coros'}]:
            self.decode.return_value = credentials
            with self.assertRaises(StsTokenError):
                AwsOssClient('private-token', 1)
        self.boto.assert_not_called()

    def test_missing_login_does_not_make_request(self):
        with self.assertRaises(StsTokenError):
            AwsOssClient('', 1)
        with self.assertRaises(ValueError):
            AwsOssClient('private-token', 2)
        self.http.request.assert_not_called()

    def test_storage_upload_failure_reaches_caller(self):
        client = AwsOssClient('private-token', 1)
        client.client.upload_file.side_effect = RuntimeError('upload failed')
        with self.assertRaisesRegex(RuntimeError, 'upload failed'):
            client.multipart_upload('activity.zip', 'user/activity.zip')

    def test_import_non_json_response_raises_instead_of_exiting_successfully(self):
        client = CorosClient('email', 'password')
        client.accessToken, client.regionId, client.teamapi = 'private-token', 1, 'https://teamapi.coros.com'
        client.req = Mock()
        client.req.request.return_value.data = b'<html>private response</html>'
        with redirect_stdout(StringIO()), self.assertRaises(CorosActivityUploadError) as error:
            client.uploadActivity('fit_zip/user/activity.zip', 'md5', 'activity.zip', 4)
        self.assertNotIn('private', str(error.exception))


class GarminToCorosFailureTests(unittest.TestCase):
    def test_storage_setup_failure_stops_once_and_preserves_unsynced_status(self):
        with ExitStack() as stack:
            stack.enter_context(redirect_stdout(StringIO()))
            garmin = stack.enter_context(patch('garmin.garmin_client.GarminClient')).return_value
            coros = stack.enter_context(patch('coros.coros_client.CorosClient')).return_value
            database = stack.enter_context(patch('garmin.garmin_db.GarminDB')).return_value
            aws = stack.enter_context(patch('oss.aws_oss_client.AwsOssClient'))
            stack.enter_context(patch('oss.ali_oss_client.AliOssClient'))
            stack.enter_context(patch('builtins.open'))
            stack.enter_context(patch('os.path.exists', return_value=True))
            garmin.getAllActivities.return_value = [{'activityId': 1}, {'activityId': 2}]
            garmin.downloadFitActivity.return_value = b'zip'
            database.getUnSyncActivity.return_value = [1, 2]
            coros.regionId, coros.accessToken = 1, 'private-token'
            aws.side_effect = StsTokenError('HTTP 404')
            with self.assertRaises(SystemExit) as error:
                runpy.run_path(str(Path(__file__).resolve().parents[1] / 'garmin/garmin_sync_coros.py'), run_name='__main__')
            self.assertEqual(error.exception.code, 1)
            aws.assert_called_once_with(access_token='private-token', region_id=1)
            database.updateSyncStatus.assert_not_called()
            coros.uploadActivity.assert_not_called()

    def test_download_upload_and_import_failures_exit_with_failure(self):
        for stage in ('download', 'upload', 'import'):
            with self.subTest(stage=stage), ExitStack() as stack:
                stack.enter_context(redirect_stdout(StringIO()))
                garmin = stack.enter_context(patch('garmin.garmin_client.GarminClient')).return_value
                coros = stack.enter_context(patch('coros.coros_client.CorosClient')).return_value
                database = stack.enter_context(patch('garmin.garmin_db.GarminDB')).return_value
                aws = stack.enter_context(patch('oss.aws_oss_client.AwsOssClient')).return_value
                stack.enter_context(patch('oss.ali_oss_client.AliOssClient'))
                stack.enter_context(patch('builtins.open'))
                stack.enter_context(patch('os.path.exists', return_value=True))
                stack.enter_context(patch('os.path.getsize', return_value=4))
                stack.enter_context(patch('utils.md5_utils.calculate_md5_file', return_value='md5'))
                garmin.getAllActivities.return_value = [{'activityId': 1}]
                garmin.downloadFitActivity.return_value = b'zip'
                database.getUnSyncActivity.return_value = [1]
                coros.regionId, coros.accessToken = 1, 'private-token'
                if stage == 'download':
                    garmin.downloadFitActivity.side_effect = RuntimeError('download failed')
                elif stage == 'upload':
                    aws.multipart_upload.side_effect = RuntimeError('upload failed')
                else:
                    coros.uploadActivity.return_value = False
                with self.assertRaises(SystemExit) as error:
                    runpy.run_path(str(Path(__file__).resolve().parents[1] / 'garmin/garmin_sync_coros.py'), run_name='__main__')
                self.assertEqual(error.exception.code, 1)
                database.updateSyncStatus.assert_not_called()
                if stage != 'import':
                    coros.uploadActivity.assert_not_called()


if __name__ == '__main__':
    unittest.main()
