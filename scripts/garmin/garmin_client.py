import logging
import os
from enum import Enum, auto
from functools import wraps
from pathlib import Path
import requests

from garminconnect import Garmin


from .garmin_url_dict import GARMIN_URL_DICT

logger = logging.getLogger(__name__)


def is_duplicate_activity(detailed_import_result):
  """Return whether Garmin's import response reports a duplicate activity."""
  if not isinstance(detailed_import_result, dict):
    return False

  failures = detailed_import_result.get("failures")
  if not isinstance(failures, list):
    return False

  for failure in failures:
    if not isinstance(failure, dict):
      continue
    messages = failure.get("messages")
    if not isinstance(messages, list):
      continue
    if any(
        isinstance(message, dict)
        and message.get("content") == "Duplicate Activity."
        for message in messages
    ):
      return True
  return False


class GarminClient:
  def __init__(self, email, password, auth_domain, newest_num):
        region = str(auth_domain or 'COM').upper()
        if region not in ('COM', 'CN'):
          raise ValueError('GARMIN_AUTH_DOMAIN must be COM or CN')
        self.api = Garmin(email, password, is_cn=region == 'CN')
        self.tokenstore = os.getenv('GARMINTOKENS', str(Path(__file__).resolve().parents[2] / '.garmin-session'))
        self.logged_in = False
        self.newestNum = int(newest_num)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.88 Safari/537.36",
            "origin": f"https://sso.garmin.{'cn' if region == 'CN' else 'com'}",
            "nk": "NT"
        }
  
  ## 登录装饰器
  def login(func):    
    @wraps(func)
    def ware(self, *args, **kwargs):
      if not self.logged_in:
        try:
          self.api.login(self.tokenstore)
          self.api.client.dump(self.tokenstore)
        except Exception as err:
          raise GarminNoLoginException(
              f'Garmin login failed ({type(err).__name__}). Check credentials, region, '
              'MFA requirements, or Garmin rate limiting; do not repeatedly retry.'
          ) from None
        self.logged_in = True
      return func(self, *args, **kwargs)
    return ware
  
  @login 
  def download(self, path, **kwargs):
     return self.api.download(path, **kwargs)
  
  @login 
  def connectapi(self, path, **kwargs):
      return self.api.connectapi(path, **kwargs)
     

  ## 获取运动
  def getActivities(self, start:int, limit:int):
     
     params = {"start": str(start), "limit": str(limit)}
     activities =  self.connectapi(path=GARMIN_URL_DICT["garmin_connect_activities"], params=params)
     return activities;

  # ## 获取所有运动
  # def getAllActivities(self): 
  #   all_activities = []
  #   start = 0
  #   limit=100
  #   if 0 < self.newestNum < 100:
  #     limit = self.newestNum
      
  #   while(True):
  #     activities = self.getActivities(start=start, limit=limit)
  #     if len(activities) > 0:
  #       all_activities.extend(activities)
        
  #       if 0 < self.newestNum < 100 or start > self.newestNum:
  #          return all_activities
  #     else:
  #        return all_activities
  #     start += limit

  ## 获取所有运动
  def getAllActivities(self): 
    all_activities = []
    start = 0
    while(True):
      activities = self.getActivities(start=start, limit=100)
      if len(activities) > 0:
         all_activities.extend(activities)
      else:
         return all_activities
      start += 100

  ## 下载原始格式的运动
  def downloadFitActivity(self, activity):
    download_fit_activity_url_prefix = GARMIN_URL_DICT["garmin_connect_fit_download"]
    download_fit_activity_url = f"{download_fit_activity_url_prefix}/{activity}"
    response = self.download(download_fit_activity_url)
    return response

  @login  
  def upload_activity(self, activity_path: str):
    """Upload activity in fit format from file."""
    # This code is borrowed from python-garminconnect-enhanced ;-)
    file_base_name = os.path.basename(activity_path)
    file_extension = file_base_name.split(".")[-1]
    allowed_file_extension = (
        file_extension.upper() in ActivityUploadFormat.__members__
    )

    if allowed_file_extension:
       status = "UPLOAD_EXCEPTION"
       try:
        with open(activity_path, 'rb') as file:
          file_data = file.read()
          fields = {
              'file': (file_base_name, file_data, 'text/plain')
          }

          url_path = GARMIN_URL_DICT["garmin_connect_upload"]
          # Validate/refresh the session before the raw upload that preserves HTTP 409 details.
          self.api.connectapi('/userprofile-service/socialProfile')
          upload_url = f"https://connectapi.{self.api.client.domain}{url_path}"
          headers = {**self.headers, **self.api.client.get_api_headers()}
          response = requests.post(upload_url, headers=headers, files=fields, timeout=60)
          res_code = response.status_code
          result = response.json()
          detailed_import_result = (
              result.get("detailedImportResult")
              if isinstance(result, dict)
              else None
          )
          uploadId = (
              detailed_import_result.get("uploadId")
              if isinstance(detailed_import_result, dict)
              else None
          )
          isDuplicateUpload = uploadId == None or uploadId == ''
          if res_code == 202 and not isDuplicateUpload:
              status = "SUCCESS"
          elif res_code == 409 and is_duplicate_activity(detailed_import_result):
              status = "DUPLICATE_ACTIVITY"
          else:
              print(f"  -> HTTP {res_code}: {result}")
       except Exception as e:
            print(f"  -> exception: {e}")
            status = "UPLOAD_EXCEPTION"
       finally:
            return status
    else:
        return "UPLOAD_EXCEPTION"
  

class ActivityUploadFormat(Enum):
  FIT = auto()
  GPX = auto()
  TCX = auto()

class GarminNoLoginException(Exception):
    """Raised when rate limit is exceeded."""

    def __init__(self, status):
        """Initialize."""
        super(GarminNoLoginException, self).__init__(status)
        self.status = status
