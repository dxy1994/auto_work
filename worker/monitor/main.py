"""
监控型 Worker 入口：连接总控、注册本机、心跳保活、
领取并执行浏览器自动化任务（订单监控 + 招呼发送）。

不包含游戏交易执行能力。

运行：python -m monitor.main
"""
import asyncio
import json
import os
import sys
import threading

# ── 让 worker 目录内模块可平铺导入 ──
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common import clock
from common import config
from common.context import AppContext
from common.client import AgentClient
from common.reporter import Reporter
from common.autostart import handle_autostart_args
from monitor.task_manager import TaskManager

# 安装时间戳 print
clock.install()


def run_self_check() -> int:
    """Validate imports required by the packaged monitor without starting it."""
    import importlib
    import platform

    required_modules = (
        "websockets",
        "dotenv",
        "patchright.async_api",
        "requests",
        "boto3",
        "bs4",
        "pygame",
        "pythoncom",
        "win32com.client",
        "monitor.browser.session",
        "monitor.chat.sender",
    )
    failures = []
    for module_name in required_modules:
        try:
            importlib.import_module(module_name)
            print(f"[SelfCheck][OK] {module_name}")
        except Exception as exc:
            failures.append(f"{module_name}: {exc}")
            print(f"[SelfCheck][FAILED] {module_name}: {exc}")

    try:
        from monitor.monitoring.registry import MONITOR_REGISTRY
        missing_platforms = {1, 2, 3} - set(MONITOR_REGISTRY)
        if missing_platforms:
            raise RuntimeError(f"missing platform adapters: {sorted(missing_platforms)}")
        print(
            "[SelfCheck][OK] platform adapters: "
            + ", ".join(str(value) for value in sorted(MONITOR_REGISTRY))
        )
    except Exception as exc:
        failures.append(f"platform adapters: {exc}")
        print(f"[SelfCheck][FAILED] platform adapters: {exc}")

    print(
        f"[SelfCheck] Python={platform.python_version()} "
        f"architecture={platform.architecture()[0]} frozen={getattr(sys, 'frozen', False)}"
    )
    if failures:
        print(f"[SelfCheck] Monitor package failed with {len(failures)} problem(s).")
        return 1
    print("[SelfCheck] Monitor package is ready.")
    return 0


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
        from monitor.monitoring.base import _make_result
        from monitor.monitoring.registry import MONITOR_REGISTRY
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
            print(f"[Monitor] 订单查询异常。原因：{e}；解决方案：浏览器保持打开，"
                  "请检查网站配置和登录状态，监控循环将继续重试。")
            traceback.print_exc()
            result = _make_result(
                "failed",
                f"原因：订单查询异常：{e}；解决方案：检查网站配置和登录状态后重试。",
                start)
        return result

    def _runner(stop_event):
        if stop_event.is_set():
            result = {"status": "failed", "message": "任务已停止", "duration_ms": 0}
        else:
            try:
                result = run(msg, stop_event, account_id, task_id)
            except Exception as e:
                import traceback
                print(f"[Monitor] 任务执行异常 task_id={task_id}。原因：{e}；"
                      "解决方案：检查监控端依赖和账号配置后重新下发任务。")
                traceback.print_exc()
                result = {
                    "status": "failed",
                    "message": f"原因：浏览器任务启动失败：{e}；解决方案：检查监控端依赖和账号配置后重试。",
                    "duration_ms": 0,
                }
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

    if mtype == "order_check":
        _submit_task(msg, ctx)

    elif mtype == "cancel":
        account_id = msg.get("account_id")
        ok = task_manager.cancel(account_id)
        print(f"[Monitor] 收到 cancel account_id={account_id}, ok={ok}")

    elif mtype == "orders_check_result":
        reporter.deliver_orders_check_result(
            msg.get("request_id"), msg.get("existing_ids", []))

    elif mtype in {"chat", "greeting"}:
        # 聊天指令：优先路由到持有订单来源账号会话的活跃 Monitor。
        account_id = msg.get("account_id")
        from monitor.monitoring.base import get_active_monitor
        monitor = get_active_monitor(account_id) if account_id else None
        if monitor:
            threading.Thread(
                target=lambda: monitor.do_chat(msg),
                daemon=True,
                name=f"chat-{msg.get('order_id', 'unknown')}",
            ).start()
        else:
            from monitor.monitoring.chat import handle_chat
            threading.Thread(
                target=handle_chat,
                args=(msg, reporter),
                kwargs={"main_loop": ctx.loop},
                daemon=True,
                name=f"chat-{msg.get('order_id', 'unknown')}",
            ).start()

    else:
        print(f"[Monitor] 未知消息类型: {mtype}")


# ═══════════════════════════════════════════════════════════
# 连接管理
# ═══════════════════════════════════════════════════════════

async def _heartbeat(client, ctx: AppContext):
    while True:
        await asyncio.sleep(config.HEARTBEAT_INTERVAL)
        await client.send({
            "type": "heartbeat",
            "runtime": {"role": "monitor"},
        })


async def _connect_once(ctx: AppContext):
    import websockets

    info = config.get_machine_info()
    info["role"] = "monitor"
    async with websockets.connect(config.BACKEND_WS_URL, max_size=None) as ws:
        loop = asyncio.get_event_loop()
        client = AgentClient(ws, loop)
        try:
            reporter = ctx.reporter
            reporter.set_client(client)
            print("[Monitor] 已将现有监控任务切换到新的总控连接")
        except RuntimeError:
            reporter = Reporter(client)
            ctx.reporter = reporter

        await client.send({"type": "register", **info})
        print(f"[Monitor] 已连接总控，注册中: {info}")

        hb = asyncio.create_task(_heartbeat(client, ctx))
        try:
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except Exception:
                    continue
                if msg.get("type") == "registered":
                    print(f"[Monitor] 注册成功 machine_id={msg.get('machine_id')}")
                    continue
                await _dispatch_message(msg, ctx)
        finally:
            hb.cancel()
            print("[Monitor] 与总控连接已断开，现有监控任务和浏览器保持运行，等待自动重连")


async def main_loop():
    loop = asyncio.get_event_loop()
    ctx = AppContext(loop)

    # 跨重连复用注册表；未及时退出的旧任务继续占用账号，避免新连接重复启动。
    task_manager = TaskManager()
    ctx.task_manager = task_manager

    while True:
        try:
            await _connect_once(ctx)
        except Exception as e:
            print(f"[Monitor] 总控连接异常。原因：{e}；解决方案：浏览器和监控任务保持运行，"
                  f"{config.RECONNECT_INTERVAL}s 后自动重连。")
        await asyncio.sleep(config.RECONNECT_INTERVAL)


def start():
    """启动独立的监控 Worker。"""
    print(f"[Monitor] 启动，总控地址: {config.BACKEND_WS_URL}")
    asyncio.run(main_loop())


if __name__ == "__main__":
    if "--self-check" in sys.argv:
        sys.exit(run_self_check())
    autostart_result = handle_autostart_args("auto-monitor")
    if autostart_result is not None:
        sys.exit(autostart_result)
    start()
