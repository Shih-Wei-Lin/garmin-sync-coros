import os

from dotenv import load_dotenv

# getting content root directory
current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)

# 本地开发时从 .env 读取；面板变量或 GitHub Actions 的环境变量优先，不会被覆盖
load_dotenv(os.path.join(parent, ".env"))

SYS_CONFIG = {}

# 首先读取 面板变量 或者 github action 运行变量
for k in SYS_CONFIG:
    if os.getenv(k):
        v = os.getenv(k)
        SYS_CONFIG[k] = v


GARMIN_FIT_DIR = os.path.join(parent, "garmin-fit")
COROS_FIT_DIR = os.path.join(parent, "coros-fit")

DB_DIR =  os.path.join(parent, "db")
