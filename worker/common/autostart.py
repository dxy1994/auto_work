"""Windows 打包程序的开机自启管理。"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional


def _shortcut_path(app_name: str) -> Path:
    startup = Path(os.environ.get("APPDATA", "")) / (
        "Microsoft/Windows/Start Menu/Programs/Startup"
    )
    return startup / f"{app_name}.lnk"


def _ps_literal(value: str) -> str:
    return value.replace("'", "''")


def handle_autostart_args(app_name: str) -> Optional[int]:
    """处理 ``--install`` / ``--uninstall``；无相关参数时返回 None。"""
    install = "--install" in sys.argv
    uninstall = "--uninstall" in sys.argv
    if not install and not uninstall:
        return None
    if sys.platform != "win32":
        print("[Autostart] 仅支持 Windows")
        return 1

    shortcut = _shortcut_path(app_name)
    if uninstall:
        if shortcut.exists():
            shortcut.unlink()
            print(f"[Autostart] 已移除: {shortcut}")
        return 0

    if not getattr(sys, "frozen", False):
        print("[Autostart] 请使用打包后的 EXE 执行 --install")
        return 1

    executable = Path(sys.executable).resolve()
    command = (
        "$ws = New-Object -ComObject WScript.Shell; "
        f"$sc = $ws.CreateShortcut('{_ps_literal(str(shortcut))}'); "
        f"$sc.TargetPath = '{_ps_literal(str(executable))}'; "
        f"$sc.WorkingDirectory = '{_ps_literal(str(executable.parent))}'; "
        f"$sc.Description = '{_ps_literal(app_name)}'; "
        "$sc.WindowStyle = 7; $sc.Save()"
    )
    try:
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                command,
            ],
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        print(f"[Autostart] 配置失败: {exc}")
        return 1
    print(f"[Autostart] 已启用: {shortcut}")
    return 0
