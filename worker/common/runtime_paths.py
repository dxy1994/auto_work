"""Worker 在源码运行和 PyInstaller EXE 中使用的持久化路径。"""
import os
import sys
from pathlib import Path


def monitor_user_data_root() -> Path:
    """返回不会随 one-file EXE 临时解包目录消失的浏览器资料目录。"""
    configured = os.getenv("MONITOR_USER_DATA_DIR", "").strip()
    if configured:
        return Path(os.path.expandvars(configured)).expanduser().resolve()
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "user_data"
    return Path(__file__).resolve().parent.parent / "user_data"
