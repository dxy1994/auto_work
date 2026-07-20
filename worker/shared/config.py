"""
worker 配置与本机信息检测。

通过 worker/.env 或环境变量覆盖：
  BACKEND_WS_URL         总控 Agent 接入点，如 ws://127.0.0.1:8000/api/agent/ws
  PLAYWRIGHT_HEADLESS    是否无头运行浏览器
  HEARTBEAT_INTERVAL     心跳间隔（秒）
  RECONNECT_INTERVAL     断线重连间隔（秒）
  STORAGE_ENDPOINT       RustFS / S3 兼容存储地址（留空则不启用远程同步）
  STORAGE_BUCKET         存储桶名称
  STORAGE_ACCESS_KEY     存储 Access Key
  STORAGE_SECRET_KEY     存储 Secret Key
  STORAGE_REGION         存储 Region
  STORAGE_PATH_STYLE     是否使用 path-style 访问（RustFS 需 true）
  WORKER_ROLE            Worker 角色：monitor / trader（默认 monitor）
"""
import os
import platform
import socket
import uuid
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except Exception:
    pass

# ── 总控 WebSocket 接入点 ──
BACKEND_WS_URL = os.getenv("BACKEND_WS_URL", "ws://127.0.0.1:8000/api/agent/ws")

# ── Docker/无人值守时用 headless，本地开发保持有头 ──
PLAYWRIGHT_HEADLESS = os.getenv("PLAYWRIGHT_HEADLESS", "false").lower() in ("true", "1", "yes")

# ── 心跳与重连 ──
HEARTBEAT_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL", "20"))
RECONNECT_INTERVAL = int(os.getenv("RECONNECT_INTERVAL", "5"))

# Trader 键鼠硬件网关
ESP32_HOST = os.getenv("ESP32_HOST", "192.168.1.100")

# ── RustFS / S3 兼容存储（浏览器配置跨机器同步）──
STORAGE_ENDPOINT = os.getenv("STORAGE_ENDPOINT", "")
STORAGE_BUCKET = os.getenv("STORAGE_BUCKET", "auto-worker-profiles")
STORAGE_ACCESS_KEY = os.getenv("STORAGE_ACCESS_KEY", "")
STORAGE_SECRET_KEY = os.getenv("STORAGE_SECRET_KEY", "")
STORAGE_REGION = os.getenv("STORAGE_REGION", "us-east-1")
STORAGE_PATH_STYLE = os.getenv("STORAGE_PATH_STYLE", "true").lower() in ("true", "1", "yes")
STORAGE_PUBLIC_BASE_URL = os.getenv("STORAGE_PUBLIC_BASE_URL", "")

# ── Worker 角色 ──
WORKER_ROLE = os.getenv("WORKER_ROLE", "monitor")


def get_mac_address() -> str:
    """获取本机 MAC 地址，格式 AA:BB:CC:DD:EE:FF"""
    mac = uuid.getnode()
    mac_hex = f"{mac:012X}"
    return ":".join(mac_hex[i:i + 2] for i in range(0, 12, 2))


def get_machine_info() -> dict:
    """采集本机信息用于向总控注册。"""
    hostname = socket.gethostname()
    try:
        ip = socket.gethostbyname(hostname)
    except Exception:
        ip = "127.0.0.1"
    return {
        "mac": get_mac_address(),
        "hostname": hostname,
        "ip": ip,
        "os": f"{platform.system()} {platform.release()}",
    }
