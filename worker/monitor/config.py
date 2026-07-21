"""监控主机专用配置。"""

import os


PLAYWRIGHT_HEADLESS = os.getenv("PLAYWRIGHT_HEADLESS", "false").lower() in (
    "true",
    "1",
    "yes",
)

STORAGE_ENDPOINT = os.getenv("STORAGE_ENDPOINT", "")
STORAGE_BUCKET = os.getenv("STORAGE_BUCKET", "auto-worker-profiles")
STORAGE_ACCESS_KEY = os.getenv("STORAGE_ACCESS_KEY", "")
STORAGE_SECRET_KEY = os.getenv("STORAGE_SECRET_KEY", "")
STORAGE_REGION = os.getenv("STORAGE_REGION", "us-east-1")
STORAGE_PATH_STYLE = os.getenv("STORAGE_PATH_STYLE", "true").lower() in (
    "true",
    "1",
    "yes",
)
STORAGE_PUBLIC_BASE_URL = os.getenv("STORAGE_PUBLIC_BASE_URL", "")
