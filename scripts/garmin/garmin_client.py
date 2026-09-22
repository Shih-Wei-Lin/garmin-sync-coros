import os
from enum import Enum, auto
from pathlib import Path

from garminconnect import Garmin, GarminConnectConnectionError


from .garmin_url_dict import GARMIN_URL_DICT


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
        self.auth_domain = auth_domain
        self.email = email
        self.password = password
        self.session_dir = os.getenv(
            "GARMIN_SESSION_DIR", str(Path(__file__).resolve().parents[2] / ".garmin-session")
        )
        self.api = Garmin(
            email=email or None, password=password or None,
            is_cn=str(auth_domain).upper() == "CN", prompt_mfa=self.prompt_mfa,
        )
        self.authenticated = False
        self.newestNum = int(newest_num)

  @staticmethod
  def prompt_mfa():
    if os.getenv("GITHUB_ACTIONS") == "true":
      raise RuntimeError("Garmin requires MFA. Initialize the session locally; see README.")
    return input("Garmin MFA code: ").strip()

  def ensure_authenticated(self):
    if not self.authenticated:
      self.api.login(self.session_dir)
      self.api.client.dump(self.session_dir)
      self.authenticated = True

  ## 登录装饰器
  def login(func):    
    def ware(self, *args, **kwargs):    
      self.ensure_authenticated()
      try:
        return func(self, *args, **kwargs)
      finally:
        # The library refreshes tokens during API calls; persist the updated session.
        self.api.client.dump(self.session_dir)
    return ware
  
  @login 
  def download(self, path, **kwargs):
     return self.api.client.download(path, **kwargs)
  
  @login 
  def connectapi(self, path, **kwargs):
      return self.api.client.connectapi(path, **kwargs)
     

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
          result = self.api.upload_activity(activity_path)
          detailed_import_result = result.get("detailedImportResult") if isinstance(result, dict) else None
          if isinstance(detailed_import_result, dict) and detailed_import_result.get("uploadId"):
              status = "SUCCESS"
          elif is_duplicate_activity(detailed_import_result):
              status = "DUPLICATE_ACTIVITY"
       except GarminConnectConnectionError as error:
          # The library raises for HTTP 409 instead of returning its JSON body.
          message = str(error)
          if message.startswith("API Error 409 - ") and "Duplicate Activity." in message:
              status = "DUPLICATE_ACTIVITY"
          else:
              print(f"  -> Garmin upload failed: {message}")
       except Exception as error:
          print(f"  -> Garmin upload failed ({type(error).__name__})")
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
