"""游戏执行主机专用配置。"""

import os


STORAGE_ENDPOINT = os.getenv("STORAGE_ENDPOINT", "").strip()
STORAGE_BUCKET = os.getenv("STORAGE_BUCKET", "auto-uploads").strip()
STORAGE_ACCESS_KEY = os.getenv("STORAGE_ACCESS_KEY", "").strip()
STORAGE_SECRET_KEY = os.getenv("STORAGE_SECRET_KEY", "").strip()
STORAGE_REGION = os.getenv("STORAGE_REGION", "us-east-1").strip()
STORAGE_PATH_STYLE = os.getenv("STORAGE_PATH_STYLE", "true").lower() in (
    "true",
    "1",
    "yes",
)
