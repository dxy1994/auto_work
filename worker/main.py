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
import threading

# ── 让 worker 目录内模块可平铺导入 ──
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import websockets

from core import clock
from core import config
from core.context import AppContext
from ws.client import AgentClient
from ws.reporter import Reporter
from task_manager import TaskManager
from trade.status import RuntimeStatus
from trade.gate import TradeTaskGate

# 安装时间戳 print
clock.install()


# ═══════════════════════════════════════════════════════════
# 开机自启管理（仅 Windows EXE 模式有效）
# ═══════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════
# 任务处理
# ═══════════════════════════════════════════════════════════

def _submit_task(msg, ctx: AppContext):
    """通用任务提交：执行 run_func 并通过 reporter 回报结果。"""
    reporter = ctx.reporter
    task_manager = ctx.task_manager
    task_id = msg["task_id"]
    account_id = msg.get("account_id")

    def run(msg, stop_event, account_id, task_id):
        from monitoring.base import _make_result
        from monitoring.registry import MONITOR_REGISTRY
        import time

        start = time.time()
        website_id = msg.get("website_id")
        monitor_cls = MONITOR_REGISTRY.get(website_id)
        if monitor_cls is None:
            return _make_result(
                "skipped", f"网站 ID {website_id} 未配置订单查询逻辑", start)

        result = None
        try:
            monitor = monitor_cls(
                task_id=task_id,
                website_id=website_id,
                account_id=account_id,
                start=start,
                reporter=reporter,
                login_url=msg.get("url"),
                username=msg.get("username"),
                password=msg.get("password"),
                login_type=msg.get("login_type", "form"),
                login_config=msg.get("login_config") or {},
                stop_event=stop_event,
                force_login=msg.get("force_login", False),
            )
            result = asyncio.run(monitor.run())
        except Exception as e:
            import traceback
            print(f"[Worker] 订单查询异常: {e}")
            traceback.print_exc()
            result = _make_result("failed", f"订单查询异常：{e}", start)
        return result

    def _runner(stop_event):
        if stop_event.is_set():
            result = {"status": "failed", "message": "任务已停止", "duration_ms": 0}
        else:
            try:
                result = run(msg, stop_event, account_id, task_id)
            except Exception as e:
                import traceback
                print(f"[Worker] 任务执行异常 (task_id={task_id}): {e}")
                traceback.print_exc()
                result = {"status": "failed", "message": f"浏览器任务启动失败：{e}", "duration_ms": 0}
        reporter.report_result(task_id, account_id, result)

    started = task_manager.start_order_check(task_id, account_id, _runner)
    if not started:
        reporter.report_result(task_id, account_id, {
            "status": "failed",
            "message": "该账号已有任务在运行",
            "duration_ms": 0,
        })


# ═══════════════════════════════════════════════════════════
# 消息分发
# ═══════════════════════════════════════════════════════════

async def _dispatch_message(msg, ctx: AppContext):
    """根据消息类型分发到不同处理函数。"""
    mtype = msg.get("type")
    reporter = ctx.reporter
    task_manager = ctx.task_manager
    runtime_status = ctx.runtime_status
    trade_task_gate = ctx.trade_task_gate

    if mtype == "order_check":
        _submit_task(msg, ctx)

    elif mtype == "cancel":
        account_id = msg.get("account_id")
        ok = task_manager.cancel(account_id)
        print(f"[Worker] 收到 cancel account_id={account_id}, ok={ok}")

    elif mtype == "orders_check_result":
        reporter.deliver_orders_check_result(
            msg.get("request_id"), msg.get("existing_ids", []))

    elif mtype == "trade_offer":
        assignment_id = msg.get("assignment_id")
        accepted, reason = trade_task_gate.offer(
            assignment_id, msg.get("execution_token"))
        if accepted:
            runtime_status.update(
                executor_status="reserved",
                current_assignment_id=assignment_id,
            )
        reporter.report_trade_offer_decision(
            assignment_id, accepted, "" if accepted else reason)

    elif mtype == "trade_start":
        assignment_id = msg.get("assignment_id")
        if trade_task_gate.start(assignment_id, msg.get("execution_token")):
            runtime_status.update(
                executor_status="running",
                current_assignment_id=assignment_id,
            )
            reporter.report_trade_status(
                assignment_id, "started", "simulation runner started")
            reporter.report_trade_status(
                assignment_id, "simulation_completed", "no game input executed")
            trade_task_gate.complete(assignment_id)
            runtime_status.update(
                executor_status="idle",
                current_assignment_id=None,
            )
        else:
            reporter.report_trade_status(
                assignment_id, "start_rejected", "assignment or token mismatch")

    elif mtype == "trade_cancel":
        assignment_id = msg.get("assignment_id")
        if trade_task_gate.cancel(assignment_id):
            runtime_status.update(
                executor_status="idle",
                current_assignment_id=None,
            )
            reporter.report_trade_status(assignment_id, "cancelled")

    elif mtype == "greeting":
        # 招呼指令：优先路由到活跃 Monitor（复用其 session，避免 CDP 争抢）
        account_id = msg.get("account_id")
        from monitoring.base import get_active_monitor
        monitor = get_active_monitor(account_id) if account_id else None
        if monitor:
            threading.Thread(
                target=lambda: monitor.do_greeting(msg),
                daemon=True,
                name=f"greeting-{msg.get('order_id', 'unknown')}",
            ).start()
        else:
            from monitoring.greeting import handle_greeting
            threading.Thread(
                target=handle_greeting,
                args=(msg, reporter),
                kwargs={"main_loop": ctx.loop},
                daemon=True,
                name=f"greeting-{msg.get('order_id', 'unknown')}",
            ).start()

    else:
        print(f"[Worker] 未知消息类型: {mtype}")


# ═══════════════════════════════════════════════════════════
# 连接管理
# ═══════════════════════════════════════════════════════════

async def _heartbeat(client, ctx: AppContext):
    while True:
        await asyncio.sleep(config.HEARTBEAT_INTERVAL)
        await client.send({
            "type": "heartbeat",
            "runtime": ctx.runtime_status.snapshot(),
        })


async def _connect_once(ctx: AppContext):
    info = config.get_machine_info()
    async with websockets.connect(config.BACKEND_WS_URL, max_size=None) as ws:
        loop = asyncio.get_event_loop()
        client = AgentClient(ws, loop)
        reporter = Reporter(client)
        ctx.reporter = reporter

        await client.send({"type": "register", **info})
        print(f"[Worker] 已连接总控，注册中: {info}")

        hb = asyncio.create_task(_heartbeat(client, ctx))
        try:
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except Exception:
                    continue
                if msg.get("type") == "registered":
                    print(f"[Worker] 注册成功 machine_id={msg.get('machine_id')}")
                    continue
                await _dispatch_message(msg, ctx)
        finally:
            hb.cancel()
            ctx.task_manager.cancel_all()


async def _main_loop():
    loop = asyncio.get_event_loop()
    ctx = AppContext(loop)

    runtime_status = RuntimeStatus()
    trade_task_gate = TradeTaskGate()
    ctx.runtime_status = runtime_status
    ctx.trade_task_gate = trade_task_gate

    # 跨重连复用注册表；未及时退出的旧任务继续占用账号，避免新连接重复启动。
    task_manager = TaskManager()
    ctx.task_manager = task_manager

    while True:
        try:
            await _connect_once(ctx)
        except Exception as e:
            print(f"[Worker] 连接断开/失败: {e}，{config.RECONNECT_INTERVAL}s 后重连")
        await asyncio.sleep(config.RECONNECT_INTERVAL)


if __name__ == "__main__":
    if "--install" in sys.argv:
        ok = _install_autostart()
        sys.exit(0 if ok else 1)

    if "--uninstall" in sys.argv:
        ok = _uninstall_autostart()
        sys.exit(0 if ok else 1)

    print(f"[Worker] 启动，总控地址: {config.BACKEND_WS_URL}")
    try:
        asyncio.run(_main_loop())
    except KeyboardInterrupt:
        print("[Worker] 退出")
