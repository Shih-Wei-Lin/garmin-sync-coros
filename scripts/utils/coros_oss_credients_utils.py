
import base64

import hashlib

import json

## COROS training-hub 前端(coros-traininghub-v2 main bundle)里 openapi.post/get
## 用同一个 app_secret 对请求参数做签名；从官方 JS 反解出来的常量，
## 不是每个 bucket 各自一个固定值——固定 sign 只对当初算出它的那组参数
## (bucket/service/app_id/v) 有效，换 bucket 就会 401 signature error。
APP_SECRET = "e03f8a02bd61636076a0c4a87320a5f4"


def sign_params(params, secret=APP_SECRET):
  """Reimplementation of COROS web app's signParams(): sort the keys,
  concatenate key+value pairs (list/dict values become ''), append the
  secret, then uppercase MD5. Must match exactly or COROS's OSS STS
  endpoint returns a signature error.
  """
  keys = sorted(params.keys())
  raw = ""
  for key in keys:
    value = params[key]
    if isinstance(value, (list, dict)):
      value = ""
    raw += f"{key}{value}"
  raw += secret
  return hashlib.md5(raw.encode()).hexdigest().upper()


def decode(credient):
  salt = "9y78gpoERW4lBNYL"  # 盐值

  # 第一步：去除盐（salt）部分
  encode_credient = credient.replace(salt, '')

  # 第二步：Base64 解码
  credients = base64.b64decode(encode_credient).decode('utf-8')  # 解码后的内容转成 utf-8 字符串

  return json.loads(credients)
