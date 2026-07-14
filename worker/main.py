"""
分布式 worker 入口：连接总控、注册本机、心跳保活、领取并执行浏览器自动化任务。

运行：python -m worker.main  （或在 worker 目录内 python main.py）

EXE 附加命令：
  auto-worker.exe --install      配置开机自启（写入启动文件夹快捷方式）
  auto-worker.exe --uninstall    取消开机自启
"""
import asyncio
import json
import os
import subprocess
import sys

# 让 worker 目录内模块可平铺导入（与 backend 风格一致）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import websockets

import config
from agent_client import AgentClient
from reporter import Reporter, set_reporter
from task_manager import TaskManager
from automation.browser import run_auto_login, run_manual_login
from automation.order_monitor import run_order_check


# ═══════════════════════════════════════════════════════════
# 开机自启管理（仅 Windows EXE 模式有效）
# ═══════════════════════════════════════════════════════════

def _get_startup_shortcut_path() -> str:
    """Windows 当前用户启动文件夹下的快捷方式路径。"""
    startup_dir = os.path.join(
        os.environ.get("APPDATA", ""),
        r"Microsoft\Windows\Start Menu\Programs\Startup",
    )
    return os.path.join(startup_dir, "auto-worker.lnk")


def _install_autostart() -> bool:
    """创建指向当前 EXE 的快捷方式到 Windows 启动文件夹。"""
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
        print(f"[Autostart] 开机自启已启用 → {shortcut_path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[Autostart] 配置失败: {e.stderr.decode() if e.stderr else e}")
        return False


def _uninstall_autostart() -> bool:
    """从 Windows 启动文件夹中移除快捷方式。"""
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


# ═══════════════════════════════════════════════════════════
# 任务处理
# ═══════════════════════════════════════════════════════════

def _handle_login(msg, reporter, task_manager):
    task_id = msg["task_id"]
    account_id = msg.get("account_id")

    def _runner(stop_event):
        if stop_event.is_set():
            result = {"status": "failed", "message": "任务已停止", "duration_ms": 0}
        else:
            try:
                result = run_auto_login(
                    task_id=task_id,
                    url=msg["url"],
                    username=msg["username"],
                    password=msg["password"],
                    login_type=msg.get("login_type", "form"),
                    login_config=msg.get("login_config") or {},
                    website_id=msg.get("website_id"),
                    account_id=account_id,
                    stop_event=stop_event,
                )
            except Exception as e:
                result = {"status": "failed", "message": f"浏览器任务启动失败：{e}", "duration_ms": 0}
        reporter.report_result(task_id, account_id, result)

    if not task_manager.run_login(task_id, account_id, _runner):
        reporter.report_result(task_id, account_id, {
            "status": "failed",
            "message": "该账号已有任务在运行",
            "duration_ms": 0,
        })


def _handle_manual_login(msg, reporter, task_manager):
    task_id = msg["task_id"]
    account_id = msg.get("account_id")

    def _runner(stop_event):
        if stop_event.is_set():
            result = {"status": "failed", "message": "任务已停止", "duration_ms": 0}
        else:
            try:
                result = run_manual_login(
                    task_id=task_id,
                    url=msg["url"],
                    username=msg["username"],
                    password=msg["password"],
                    login_config=msg.get("login_config") or {},
                    website_id=msg.get("website_id"),
                    account_id=account_id,
                    stop_event=stop_event,
                )
            except Exception as e:
                result = {"status": "failed", "message": f"浏览器任务启动失败：{e}", "duration_ms": 0}
        reporter.report_result(task_id, account_id, result)

    if not task_manager.run_login(task_id, account_id, _runner):
        reporter.report_result(task_id, account_id, {
            "status": "failed",
            "message": "该账号已有任务在运行",
            "duration_ms": 0,
        })


def _handle_order_check(msg, reporter, task_manager):
    task_id = msg["task_id"]
    account_id = msg.get("account_id")

    def _runner(stop_event):
        try:
            result = run_order_check(
                task_id=task_id,
                website_id=msg.get("website_id"),
                account_id=account_id,
                url=msg.get("url"),
                username=msg.get("username"),
                password=msg.get("password"),
                login_type=msg.get("login_type", "form"),
                login_config=msg.get("login_config") or {},
                stop_event=stop_event,
            )
        except Exception as e:
            result = {"status": "failed", "message": f"浏览器任务启动失败：{e}", "duration_ms": 0}
        reporter.report_result(task_id, account_id, result)

    started = task_manager.start_order_check(task_id, account_id, _runner)
    if not started:
        reporter.report_result(task_id, account_id, {
            "status": "failed",
            "message": "该账号已有任务在运行",
            "duration_ms": 0,
        })


async def _dispatch_message(msg, reporter, task_manager):
    mtype = msg.get("type")
    if mtype == "login":
        _handle_login(msg, reporter, task_manager)
    elif mtype == "manual_login":
        _handle_manual_login(msg, reporter, task_manager)
    elif mtype == "order_check":
        _handle_order_check(msg, reporter, task_manager)
    elif mtype == "cancel":
        account_id = msg.get("account_id")
        ok = task_manager.cancel(account_id)
        print(f"[Worker] 收到 cancel account_id={account_id}, ok={ok}")
    elif mtype == "captcha_input":
        reporter.deliver_captcha(msg.get("task_id"), msg.get("value", ""))
    else:
        print(f"[Worker] 未知消息类型: {mtype}")


# ═══════════════════════════════════════════════════════════
# 连接管理
# ═══════════════════════════════════════════════════════════

async def _heartbeat(client):
    while True:
        await asyncio.sleep(config.HEARTBEAT_INTERVAL)
        await client.send({"type": "heartbeat"})


async def _connect_once(task_manager):
    info = config.get_machine_info()
    async with websockets.connect(config.BACKEND_WS_URL, max_size=None) as ws:
        loop = asyncio.get_event_loop()
        client = AgentClient(ws, loop)
        reporter = Reporter(client)
        set_reporter(reporter)
        # 注册本机
        await client.send({"type": "register", **info})
        print(f"[Worker] 已连接总控，注册中: {info}")

        hb = asyncio.create_task(_heartbeat(client))
        try:
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except Exception:
                    continue
                if msg.get("type") == "registered":
                    print(f"[Worker] 注册成功 machine_id={msg.get('machine_id')}")
                    continue
                await _dispatch_message(msg, reporter, task_manager)
        finally:
            hb.cancel()
            task_manager.cancel_all()


async def _main_loop():
    # 跨重连复用注册表；未及时退出的旧任务继续占用账号，避免新连接重复启动。
    task_manager = TaskManager(reporter=None)
    while True:
        try:
            await _connect_once(task_manager)
        except Exception as e:
            print(f"[Worker] 连接断开/失败: {e}，{config.RECONNECT_INTERVAL}s 后重连")
        await asyncio.sleep(config.RECONNECT_INTERVAL)


if __name__ == "__main__":
    # ── 命令行模式：开机自启管理 ──
    if "--install" in sys.argv:
        ok = _install_autostart()
        sys.exit(0 if ok else 1)

    if "--uninstall" in sys.argv:
        ok = _uninstall_autostart()
        sys.exit(0 if ok else 1)

    # ── 正常模式：启动 Worker ──
    print(f"[Worker] 启动，总控地址: {config.BACKEND_WS_URL}")
    try:
        asyncio.run(_main_loop())
    except KeyboardInterrupt:
        print("[Worker] 退出")
