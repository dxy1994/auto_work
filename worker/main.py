"""
分布式 Worker 入口：根据 WORKER_ROLE 环境变量分流到对应角色。

运行：
  python -m worker.main                          （默认 monitor 角色）
  set WORKER_ROLE=trader && python -m worker.main
  set WORKER_ROLE=monitor && python -m worker.main

EXE 附加命令：
  auto-worker.exe --install      配置开机自启（写入启动文件夹快捷方式）
  auto-worker.exe --uninstall    取消开机自启

角色说明：
  monitor  - 监控型 Worker：订单监控 + 招呼发送（需要浏览器）
  trader   - 交易型 Worker：游戏交易执行 + ESP32C3 键鼠硬件（不需要浏览器）
"""
import os
import subprocess
import sys

# ── 让 worker 目录内模块可平铺导入 ──
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from shared import clock
from shared import config

# 安装时间戳 print
clock.install()


# ── 开机自启管理（仅 Windows EXE 模式有效）──

def _get_startup_shortcut_path() -> str:
    startup_dir = os.path.join(
        os.environ.get("APPDATA", ""),
        r"Microsoft\Windows\Start Menu\Programs\Startup",
    )
    return os.path.join(startup_dir, "auto-worker.lnk")


def _install_autostart() -> bool:
    if sys.platform != "win32":
        print("[Autostart] 仅支持 Windows 平台")
        return False

    if not getattr(sys, "frozen", False):
        print("[Autostart] 当前运行在 Python 解释器下，请使用打包后的 EXE 配置开机自启")
        print("[Autostart]   或运行: scripts\\setup-autostart.bat")
        return False

    exe_path = sys.executable
    shortcut_path = _get_startup_shortcut_path()
    working_dir = os.path.dirname(exe_path)

    ps_cmd = (
        f"$ws = New-Object -ComObject WScript.Shell; "
        f"$sc = $ws.CreateShortcut('{shortcut_path}'); "
        f"$sc.TargetPath = '{exe_path}'; "
        f"$sc.WorkingDirectory = '{working_dir}'; "
        f"$sc.Description = 'Auto Worker Agent'; "
        f"$sc.WindowStyle = 7; "
        f"$sc.Save()"
    )

    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
            check=True, capture_output=True,
        )
        print(f"[Autostart] 开机自启已启用 -> {shortcut_path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[Autostart] 配置失败: {e.stderr.decode() if e.stderr else e}")
        return False


def _uninstall_autostart() -> bool:
    if sys.platform != "win32":
        print("[Autostart] 仅支持 Windows 平台")
        return False

    shortcut_path = _get_startup_shortcut_path()
    if os.path.exists(shortcut_path):
        os.remove(shortcut_path)
        print("[Autostart] 开机自启已取消")
    else:
        print("[Autostart] 未找到开机自启快捷方式，可能已取消")
    return True


# ── 入口分流 ──

if __name__ == "__main__":
    if "--install" in sys.argv:
        ok = _install_autostart()
        sys.exit(0 if ok else 1)

    if "--uninstall" in sys.argv:
        ok = _uninstall_autostart()
        sys.exit(0 if ok else 1)

    role = config.WORKER_ROLE.lower()
    print(f"[Worker] 角色={role}, 总控地址={config.BACKEND_WS_URL}")

    try:
        if role == "trader":
            from trader.main import start
        else:
            # 默认 monitor（兼容旧配置）
            from monitor.main import start
        start()
    except KeyboardInterrupt:
        print("[Worker] 退出")
