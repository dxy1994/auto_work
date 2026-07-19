"""
监控型 Worker 入口：连接总控、注册本机、心跳保活、
领取并执行浏览器自动化任务（订单监控 + 招呼发送）。

不包含游戏交易执行能力。

运行：python -m worker.monitor.main
"""
import asyncio
import json
import os
import sys
import threading

# ── 让 worker 目录内模块可平铺导入 ──
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import websockets

from shared import clock
from shared import config
from shared.context import AppContext
from shared.client import AgentClient
from shared.reporter import Reporter
from monitor.task_manager import TaskManager

# 安装时间戳 print
clock.install()


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
            print(f"[Monitor] 订单查询异常: {e}")
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
                print(f"[Monitor] 任务执行异常 (task_id={task_id}): {e}")
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

    if mtype == "order_check":
        _submit_task(msg, ctx)

    elif mtype == "cancel":
        account_id = msg.get("account_id")
        ok = task_manager.cancel(account_id)
        print(f"[Monitor] 收到 cancel account_id={account_id}, ok={ok}")

    elif mtype == "orders_check_result":
        reporter.deliver_orders_check_result(
            msg.get("request_id"), msg.get("existing_ids", []))

    elif mtype == "greeting":
        # 招呼指令：优先路由到活跃 Monitor（复用其 session，避免 CDP 争抢）
        account_id = msg.get("account_id")
        from monitor.monitoring.base import get_active_monitor
        monitor = get_active_monitor(account_id) if account_id else None
        if monitor:
            threading.Thread(
                target=lambda: monitor.do_greeting(msg),
                daemon=True,
                name=f"greeting-{msg.get('order_id', 'unknown')}",
            ).start()
        else:
            from monitor.monitoring.greeting import handle_greeting
            threading.Thread(
                target=handle_greeting,
                args=(msg, reporter),
                kwargs={"main_loop": ctx.loop},
                daemon=True,
                name=f"greeting-{msg.get('order_id', 'unknown')}",
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
    info = config.get_machine_info()
    info["role"] = "monitor"
    async with websockets.connect(config.BACKEND_WS_URL, max_size=None) as ws:
        loop = asyncio.get_event_loop()
        client = AgentClient(ws, loop)
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
            ctx.task_manager.cancel_all()


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
            print(f"[Monitor] 连接断开/失败: {e}，{config.RECONNECT_INTERVAL}s 后重连")
        await asyncio.sleep(config.RECONNECT_INTERVAL)


def start():
    """供顶层 main.py 调用的入口。"""
    print(f"[Monitor] 启动，总控地址: {config.BACKEND_WS_URL}")
    asyncio.run(main_loop())
