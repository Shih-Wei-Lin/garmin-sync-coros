import urllib3
import json
import boto3
import certifi

from boto3.s3.transfer import TransferConfig


from oss.sts_token_error import StsTokenError
from utils.coros_oss_credients_utils import decode
from coros.region_config import REGIONCONFIG
from coros.sts_config import STS_CONFIG

class AwsOssClient:
  def __init__(self, access_token, region_id):
    if region_id not in (1, 3):
      raise ValueError('AWS storage requires COROS region 1 or 3')
    if not access_token:
      raise StsTokenError('COROS login is required to obtain AWS upload credentials')
    self.bucket = STS_CONFIG[region_id]['bucket']
    self.region_id = region_id
    self.access_token = access_token
    self.req = urllib3.PoolManager(cert_reqs='CERT_REQUIRED', ca_certs=certifi.where())
    self.client = None
    self.initClient()
  
  def initClient(self):
        region = REGIONCONFIG[self.region_id]
        sts_token_url = f"{region['hostname']}/api/proxy/oss/sts?bucket={self.bucket}&service=aws&v=2"
        response = self.req.request(
            'GET', sts_token_url,
            headers={'Cookie': f"{region['TOKEN']}={self.access_token}"},
            timeout=20, retries=False, redirect=False,
        )
        if response.status != 200:
            raise StsTokenError(f'COROS AWS upload credentials: HTTP {response.status}')
        try:
            sts_token_response = json.loads(response.data)
            if sts_token_response['code'] != 200:
                raise StsTokenError('COROS rejected the AWS upload credential request')
            credients_json = decode(sts_token_response['data']['credentials'])
            required = ('AccessKeyId', 'SecretAccessKey', 'SessionToken', 'Region', 'Bucket')
            if not all(isinstance(credients_json.get(k), str) and credients_json[k] for k in required):
                raise ValueError('Incomplete AWS upload credentials')
            if credients_json['Bucket'] != self.bucket:
                raise ValueError('AWS bucket does not match the COROS account region')
        except (ValueError, KeyError, TypeError, AttributeError):
            raise StsTokenError('COROS AWS upload credentials: invalid response') from None
        self.client = boto3.client(
            "s3",
            aws_access_key_id=credients_json["AccessKeyId"],
            aws_secret_access_key=credients_json["SecretAccessKey"],
            aws_session_token=credients_json["SessionToken"],
            region_name=credients_json['Region'],
        )

  def multipart_upload(self, filePath, fileName):
      # 配置上传选项
      config = TransferConfig(
          multipart_threshold=1024 * 1024 * 5,  # 分片上传的阈值（5MB）
          max_concurrency=4,                   # 并发数
          multipart_chunksize=1024 * 1024 * 5,  # 分片大小（5MB）
          use_threads=True                     # 使用多线程
      )

      # 执行上传
      self.client.upload_file(
          filePath,
          Bucket=self.bucket,
          Key=f"fit_zip/{fileName}",
          Config=config
      )
      print(f"File {fileName} uploaded successfully!")



