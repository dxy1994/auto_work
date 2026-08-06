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

# 空闲和交易期间均检测服务器断线弹窗。至少连续两帧命中才执行关进程。
DISCONNECT_POLL_SECONDS = max(
    1.0,
    float(os.getenv("GAME_DISCONNECT_POLL_SECONDS", "3")),
)
DISCONNECT_CONFIRMATIONS = max(
    2,
    int(os.getenv("GAME_DISCONNECT_CONFIRMATIONS", "2")),
)
