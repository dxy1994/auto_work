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

# 安装时间戳 print
clock.install()


# ═══════════════════════════════════════════════════════════
# 消息分发
# ═══════════════════════════════════════════════════════════

async def _dispatch_message(msg, ctx: AppContext):
    """根据消息类型分发到交易处理函数。"""
    mtype = msg.get("type")
    reporter = ctx.reporter
    runtime_status = ctx.runtime_status
    trade_task_gate = ctx.trade_task_gate

    if mtype == "trade_offer":
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
                assignment_id, "started", "trade executor started")

            # TODO: 按 game_id 路由到对应 executor 执行真实交易
            # game_id = msg.get("game_id")
            # executor = _get_executor(game_id)
            # result = await executor.execute(msg.get("order"))
            # ...

            # 临时占位：模拟完成
            reporter.report_trade_status(
                assignment_id, "simulation_completed", "no game input executed (placeholder)")
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

    else:
        print(f"[Trader] 未知消息类型: {mtype}")


# ═══════════════════════════════════════════════════════════
# 连接管理
# ═══════════════════════════════════════════════════════════

async def _heartbeat(client, ctx: AppContext):
    while True:
        await asyncio.sleep(config.HEARTBEAT_INTERVAL)
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


async def main_loop():
    loop = asyncio.get_event_loop()
    ctx = AppContext(loop)

    runtime_status = RuntimeStatus()
    trade_task_gate = TradeTaskGate()
    ctx.runtime_status = runtime_status
    ctx.trade_task_gate = trade_task_gate

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
