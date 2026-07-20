"""
交易型 Worker 入口：连接总控、注册本机、心跳保活、执行游戏交易指令。

不包含浏览器、订单监控、招呼发送能力。

运行：python -m worker.trader.main
"""
import asyncio
import json
import os
import sys

# ── 让 worker 目录内模块可平铺导入 ──
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import websockets

from shared import clock
from shared import config
from shared.context import AppContext
from shared.client import AgentClient
from shared.reporter import Reporter
from trader.status import RuntimeStatus
from trader.gate import TradeTaskGate
from trader.executor.registry import EXECUTOR_REGISTRY
from trader.executor.hardware.controller import HardwareController
from trader.executor.lineage_classic import LineageClassicExecutor
from trader.executor.lineage_classic.policy import execution_timeout_seconds

# 安装时间戳 print
clock.install()


# ═══════════════════════════════════════════════════════════
# 消息分发
# ═══════════════════════════════════════════════════════════

TERMINAL_TRADE_STATUSES = {
    "completed",
    "failed",
    "retryable_failed",
    "timed_out",
    "cancelled",
    "verification_failed",
    "wait_web_confirm",
}


async def _run_trade_assignment(assignment_id, order, executor, ctx: AppContext):
    reporter = ctx.reporter
    runtime_status = ctx.runtime_status
    trade_task_gate = ctx.trade_task_gate

    def progress(status, message):
        runtime_status.update(executor_status=status)
        reporter.report_trade_status(assignment_id, status, message)

    set_progress = getattr(executor, "set_progress_callback", None)
    if callable(set_progress):
        set_progress(progress)
    set_buyer_review = getattr(executor, "set_buyer_review_callback", None)
    if callable(set_buyer_review):
        set_buyer_review(
            lambda review: reporter.report_trade_buyer_review(assignment_id, review)
        )
    set_trade_screenshot = getattr(executor, "set_trade_screenshot_callback", None)
    if callable(set_trade_screenshot):
        set_trade_screenshot(
            lambda screenshot: reporter.save_trade_game_screenshot(
                assignment_id, screenshot
            )
        )

    reporter.report_trade_status(assignment_id, "started", "trade executor started")
    try:
        result = await asyncio.wait_for(
            executor.execute(order),
            timeout=execution_timeout_seconds(order),
        )
        success = bool(result.get("success"))
        terminal_status = result.get("status", "completed" if success else "failed")
        if terminal_status not in TERMINAL_TRADE_STATUSES:
            terminal_status = "failed"
        reporter.report_trade_status(
            assignment_id,
            terminal_status,
            result.get("message", ""),
            result.get("error_code", ""),
        )
    except asyncio.TimeoutError:
        executor.cancel()
        reporter.report_trade_status(
            assignment_id,
            "verification_failed",
            "worker execution watchdog timed out; result may be uncertain",
            "EXECUTION_WATCHDOG_TIMEOUT",
        )
    except asyncio.CancelledError:
        executor.cancel()
        reporter.report_trade_status(
            assignment_id, "cancelled", "trade execution task cancelled", "TRADE_CANCELLED"
        )
        raise
    except Exception as exc:
        reporter.report_trade_status(
            assignment_id, "failed", f"executor error: {exc}", "EXECUTOR_EXCEPTION"
        )
    finally:
        if callable(set_progress):
            set_progress(None)
        if callable(set_buyer_review):
            set_buyer_review(None)
        if callable(set_trade_screenshot):
            set_trade_screenshot(None)
        trade_task_gate.complete(assignment_id)
        ctx.clear_active_trade(assignment_id)
        runtime_status.update(executor_status="idle", current_assignment_id=None)


async def _dispatch_message(msg, ctx: AppContext):
    """根据消息类型分发到交易处理函数。"""
    mtype = msg.get("type")
    reporter = ctx.reporter
    runtime_status = ctx.runtime_status
    trade_task_gate = ctx.trade_task_gate

    if mtype == "trade_offer":
        assignment_id = msg.get("assignment_id")
        order = msg.get("order") or {}
        game_code = order.get("game_code")
        executor = EXECUTOR_REGISTRY.get(game_code)
        if executor is None:
            reporter.report_trade_offer_decision(
                assignment_id, False,
                f"executor_not_configured:{game_code or 'unknown'}")
            return
        accepted, reason = trade_task_gate.offer(
            assignment_id, msg.get("execution_token"), order)
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
            order = trade_task_gate.current_order(assignment_id) or {}
            executor = EXECUTOR_REGISTRY.get(order.get("game_code"))
            if executor is None:
                reporter.report_trade_status(
                    assignment_id,
                    "failed",
                    "executor disappeared after offer acceptance",
                    "EXECUTOR_NOT_CONFIGURED",
                )
                trade_task_gate.complete(assignment_id)
                runtime_status.update(
                    executor_status="idle",
                    current_assignment_id=None,
                )
                return
            task = asyncio.create_task(
                _run_trade_assignment(assignment_id, order, executor, ctx),
                name=f"trade-{assignment_id}",
            )
            try:
                ctx.set_active_trade(assignment_id, executor, task)
            except Exception:
                executor.cancel()
                task.cancel()
                trade_task_gate.complete(assignment_id)
                runtime_status.update(executor_status="idle", current_assignment_id=None)
                raise
        else:
            reporter.report_trade_status(
                assignment_id, "start_rejected", "assignment or token mismatch")

    elif mtype == "trade_cancel":
        assignment_id = msg.get("assignment_id")
        active = ctx.active_trade(assignment_id)
        if active is not None:
            runtime_status.update(executor_status="cancelling")
            active["executor"].cancel()
        elif trade_task_gate.cancel(assignment_id):
            runtime_status.update(
                executor_status="idle",
                current_assignment_id=None,
            )
            reporter.report_trade_status(
                assignment_id, "cancelled", "trade cancelled before start", "TRADE_CANCELLED"
            )

    elif mtype == "trade_buyer_review_decision":
        assignment_id = msg.get("assignment_id")
        active = ctx.active_trade(assignment_id)
        submit_review = (
            getattr(active["executor"], "submit_buyer_review", None)
            if active is not None else None
        )
        if not callable(submit_review) or not submit_review(
            msg.get("review_id"), bool(msg.get("approved"))
        ):
            print(f"[Trader] 忽略已失效的买家审核决定: {msg.get('review_id')}")

    elif mtype == "trade_game_screenshot_saved":
        reporter.deliver_trade_game_screenshot_saved(
            msg.get("request_id"), bool(msg.get("success")))

    else:
        print(f"[Trader] 未知消息类型: {mtype}")


# ═══════════════════════════════════════════════════════════
# 连接管理
# ═══════════════════════════════════════════════════════════

async def _heartbeat(client, ctx: AppContext):
    while True:
        await asyncio.sleep(config.HEARTBEAT_INTERVAL)
        snapshot = ctx.runtime_status.snapshot()
        if snapshot.get("executor_status") == "idle":
            executor = EXECUTOR_REGISTRY.get("lineage_classic")
            probe = getattr(executor, "probe_runtime", None)
            if callable(probe):
                await asyncio.to_thread(probe)
        await client.send({
            "type": "heartbeat",
            "runtime": {
                "role": "trader",
                **ctx.runtime_status.snapshot(),
            },
        })


async def _connect_once(ctx: AppContext):
    info = config.get_machine_info()
    info["role"] = "trader"
    async with websockets.connect(config.BACKEND_WS_URL, max_size=None) as ws:
        loop = asyncio.get_event_loop()
        client = AgentClient(ws, loop)
        reporter = Reporter(client)
        ctx.reporter = reporter

        await client.send({"type": "register", **info})
        print(f"[Trader] 已连接总控，注册中: {info}")

        hb = asyncio.create_task(_heartbeat(client, ctx))
        try:
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except Exception:
                    continue
                if msg.get("type") == "registered":
                    print(f"[Trader] 注册成功 machine_id={msg.get('machine_id')}")
                    continue
                await _dispatch_message(msg, ctx)
        finally:
            hb.cancel()
            active = ctx.active_trade()
            if active is not None:
                active["executor"].cancel()
                active["task"].cancel()


async def main_loop():
    loop = asyncio.get_event_loop()
    ctx = AppContext(loop)

    runtime_status = RuntimeStatus()
    trade_task_gate = TradeTaskGate()
    ctx.runtime_status = runtime_status
    ctx.trade_task_gate = trade_task_gate

    if EXECUTOR_REGISTRY.get("lineage_classic") is None:
        hardware = HardwareController(config.ESP32_HOST)
        if not hardware.connect():
            raise RuntimeError("failed to connect trader hardware controller")
        executor = LineageClassicExecutor(hardware, runtime_status)
        EXECUTOR_REGISTRY.register(executor)
        await asyncio.to_thread(executor.probe_runtime)

    while True:
        try:
            await _connect_once(ctx)
        except Exception as e:
            print(f"[Trader] 连接断开/失败: {e}，{config.RECONNECT_INTERVAL}s 后重连")
        await asyncio.sleep(config.RECONNECT_INTERVAL)


def start():
    """供顶层 main.py 调用的入口。"""
    print(f"[Trader] 启动，总控地址: {config.BACKEND_WS_URL}")
    asyncio.run(main_loop())
