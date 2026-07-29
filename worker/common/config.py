"""公共 Worker 配置与本机信息检测。

这里只保留监控主机和游戏执行主机都需要的连接参数；角色专用参数分别位于
``monitor.config``；游戏执行机的键鼠地址由总控按机器绑定下发。
"""
import os
import platform
import re
import socket
import subprocess
import sys
import uuid
from ipaddress import IPv4Address
from pathlib import Path
from typing import Iterable, Optional

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


def _ipv4_priority(value: str) -> Optional[int]:
    """返回本机 IPv4 的选择优先级；无效、回环和链路本地地址不参与上报。"""
    try:
        address = IPv4Address(value)
    except ValueError:
        return None

    if address.is_loopback or address.is_link_local or address.is_unspecified:
        return None

    octets = address.packed
    if octets[0] == 192 and octets[1] == 168:
        return 0
    if octets[0] == 10:
        return 1
    if octets[0] == 172 and 16 <= octets[1] <= 31:
        return 2
    return 3


def choose_machine_ip(candidates: Iterable[str]) -> str:
    """从候选地址中选择内网 IPv4，优先当前项目使用的 192.168.* 网段。"""
    ranked = []
    seen = set()
    for index, raw in enumerate(candidates):
        value = str(raw or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        priority = _ipv4_priority(value)
        if priority is not None:
            ranked.append((priority, index, value))
    if not ranked:
        return "127.0.0.1"
    return min(ranked)[2]


def _parse_ipconfig_ipv4(output: str) -> list[str]:
    """解析 Windows ipconfig；不同语言版本的字段名都保留 ``IPv4`` 标识。"""
    return re.findall(
        r"IPv4[^\r\n:]*:\s*((?:\d{1,3}\.){3}\d{1,3})",
        output or "",
        flags=re.IGNORECASE,
    )


def _windows_adapter_ipv4_candidates() -> list[str]:
    """从 Windows IP Helper 命令枚举全部网卡，补足 hostname 只返回单一地址的问题。"""
    if sys.platform != "win32":
        return []
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        result = subprocess.run(
            ["ipconfig"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
            creationflags=creationflags,
        )
    except Exception:
        return []
    return _parse_ipconfig_ipv4(result.stdout)


def _local_ipv4_candidates(hostname: str) -> list[str]:
    """枚举 hostname 绑定的 IPv4；Windows 多网卡时通常会返回多个地址。"""
    candidates = []
    try:
        _name, _aliases, addresses = socket.gethostbyname_ex(hostname)
        candidates.extend(addresses)
    except Exception:
        pass
    try:
        candidates.extend(
            sockaddr[0]
            for _family, _socktype, _proto, _canonname, sockaddr
            in socket.getaddrinfo(
                hostname,
                None,
                family=socket.AF_INET,
                type=socket.SOCK_DGRAM,
            )
        )
    except Exception:
        pass
    candidates.extend(_windows_adapter_ipv4_candidates())
    try:
        candidates.append(socket.gethostbyname(hostname))
    except Exception:
        pass
    return candidates


def get_machine_ip(preferred_ip: Optional[str] = None) -> str:
    """获取向总控上报的本机地址；连接总控所用地址优先于普通枚举结果。"""
    if preferred_ip and _ipv4_priority(preferred_ip) == 0:
        return str(preferred_ip).strip()
    hostname = socket.gethostname()
    candidates = []
    if preferred_ip:
        candidates.append(preferred_ip)
    candidates.extend(_local_ipv4_candidates(hostname))
    return choose_machine_ip(candidates)


def get_machine_info(preferred_ip: Optional[str] = None) -> dict:
    """采集本机信息用于向总控注册。"""
    hostname = socket.gethostname()
    return {
        "mac": get_mac_address(),
        "hostname": hostname,
        "ip": get_machine_ip(preferred_ip),
        "os": f"{platform.system()} {platform.release()}",
    }
