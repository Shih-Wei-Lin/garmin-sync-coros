import urllib3
import json
import boto3
import certifi

from boto3.s3.transfer import TransferConfig


from oss.sts_token_error import StsTokenError
from utils.coros_oss_credients_utils import decode, sign_params

class AwsOssClient:
  def __init__(self, bucket="eu-coros", service="aws", app_id="1660188068672619112", v=2):
    self.bucket = bucket
    self.service = service
    self.app_id = app_id
    self.credentials = None
    self.access_key_id = None
    self.access_key_secret = None
    self.req = urllib3.PoolManager(cert_reqs='CERT_REQUIRED', ca_certs=certifi.where())
    self.v = v
    self.client = None
    self.initClient()

  def initClient(self):
        ## sign must be computed per-request: it's derived from bucket/service/
        ## app_id/v, so a sign hardcoded for one bucket 401s for any other.
        sign = sign_params({"bucket": self.bucket, "service": self.service, "app_id": self.app_id, "v": self.v})
        sts_token_url = f"https://faq.coros.com/openapi/oss/sts?bucket={self.bucket}&service={self.service}&app_id={self.app_id}&sign={sign}&v={self.v}"

        response = self.req.request('GET', sts_token_url)

        sts_token_response = json.loads(response.data)
        if sts_token_response["code"] != 200:
            raise StsTokenError("Get AWS OSS STS Token Exception")

        credentials = sts_token_response["data"]["credentials"]
        v = sts_token_response["data"]["v"]
        self.credentials = credentials
        self.v = v
        credients_json = decode(credentials)
        # The STS token is scoped to a specific bucket/region; use its own
        # Region/Bucket rather than the eu-coros default, otherwise uploads
        # for non-EU accounts land in the wrong bucket and COROS's import
        # (which looks up the bucket named in the upload metadata) fails silently.
        self.bucket = credients_json.get("Bucket", self.bucket)
        region = credients_json.get("Region", "eu-central-1")
        self.client = boto3.client(
            "s3",
            aws_access_key_id=credients_json["AccessKeyId"],
            aws_secret_access_key=credients_json["SecretAccessKey"],
            aws_session_token=credients_json["SessionToken"],
            endpoint_url=f'https://s3.{region}.amazonaws.com',
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
      try:
          self.client.upload_file(
              filePath,
              Bucket=self.bucket,
              Key=f"fit_zip/{fileName}",
              Config=config
          )
          print(f"File {fileName} uploaded successfully!")
      except Exception as e:
          print(f"Upload failed: {e}")



