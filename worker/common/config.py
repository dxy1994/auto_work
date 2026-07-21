"""公共 Worker 配置与本机信息检测。

这里只保留监控主机和游戏执行主机都需要的连接参数；角色专用参数分别位于
``monitor.config`` 和 ``game_executor.config``。
"""
import os
import platform
import socket
import sys
import uuid
from pathlib import Path

try:
    from dotenv import load_dotenv
    if getattr(sys, "frozen", False):
        env_file = Path(sys.executable).resolve().parent / ".env"
    else:
        env_file = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(env_file)
except Exception:
    pass

# ── 总控 WebSocket 接入点 ──
BACKEND_WS_URL = os.getenv("BACKEND_WS_URL", "ws://127.0.0.1:8000/api/agent/ws")

# ── 心跳与重连 ──
HEARTBEAT_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL", "20"))
RECONNECT_INTERVAL = int(os.getenv("RECONNECT_INTERVAL", "5"))


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
