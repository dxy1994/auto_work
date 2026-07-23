"""游戏执行 Worker 入口：连接总控、注册本机、心跳保活、执行游戏交易指令。

不包含浏览器、订单监控、招呼发送能力。

运行：python -m game_executor.main
"""
import asyncio
import json
import os
import sys

# ── 让 worker 目录内模块可平铺导入 ──
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common import clock
from common import config
from common.context import AppContext
from common.client import AgentClient
from common.reporter import Reporter
from common.autostart import handle_autostart_args
from game_executor.audio import speak_text
from game_executor.status import RuntimeStatus
from game_executor.gate import TradeTaskGate
from game_executor.executor.registry import EXECUTOR_REGISTRY
from game_executor.executor.hardware.controller import HardwareController
from game_executor.executor.hardware.manual import ManualActionHardwareController
from game_executor.executor.lineage_classic import LineageClassicExecutor
from game_executor.executor.lineage_classic.policy import execution_timeout_seconds
from game_executor import config as executor_config

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

CONNECT_RECOVERY_ATTEMPTS = 3
CONNECT_RECOVERY_INTERVAL_SECONDS = 3.0


def _create_hardware_controller():
    if executor_config.MANUAL_ACTIONS:
        return ManualActionHardwareController(
            action_wait_seconds=executor_config.MANUAL_ACTION_WAIT_SECONDS
        )
    return HardwareController(executor_config.ESP32_HOST)


async def _run_trade_assignment(assignment_id, order, executor, ctx: AppContext):
    reporter = ctx.reporter
    runtime_status = ctx.runtime_status
    trade_task_gate = ctx.trade_task_gate

    def progress(status, message):
        print(
            f"[GameExecutor][Trade] assignment_id={assignment_id} "
            f"status={status} message={message}",
            flush=True,
        )
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

    print(
        f"[GameExecutor][Trade] assignment_id={assignment_id} "
        "status=started message=trade executor started",
        flush=True,
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
        print(
            f"[GameExecutor][Trade] assignment_id={assignment_id} "
            f"status={terminal_status} "
            f"error_code={result.get('error_code', '')} "
            f"message={result.get('message', '')}",
            flush=True,
        )
        reporter.report_trade_status(
            assignment_id,
            terminal_status,
            result.get("message", ""),
            result.get("error_code", ""),
        )
    except asyncio.TimeoutError:
        executor.cancel()
        print(
            f"[GameExecutor][Trade] assignment_id={assignment_id} "
            "status=verification_failed error_code=EXECUTION_WATCHDOG_TIMEOUT "
            "message=worker execution watchdog timed out",
            flush=True,
        )
        reporter.report_trade_status(
            assignment_id,
            "verification_failed",
            "worker execution watchdog timed out; result may be uncertain",
            "EXECUTION_WATCHDOG_TIMEOUT",
        )
    except asyncio.CancelledError:
        executor.cancel()
        print(
            f"[GameExecutor][Trade] assignment_id={assignment_id} "
            "status=cancelled error_code=TRADE_CANCELLED "
            "message=trade execution task cancelled",
            flush=True,
        )
        reporter.report_trade_status(
            assignment_id, "cancelled", "trade execution task cancelled", "TRADE_CANCELLED"
        )
        raise
    except Exception as exc:
        print(
            f"[GameExecutor][Trade] assignment_id={assignment_id} "
            f"status=failed error_code=EXECUTOR_EXCEPTION message={exc}",
            flush=True,
        )
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
            print(f"[GameExecutor] 忽略已失效的买家审核决定: {msg.get('review_id')}")

    elif mtype == "trade_game_screenshot_saved":
        reporter.deliver_trade_game_screenshot_saved(
            msg.get("request_id"), bool(msg.get("success")))

    else:
        print(f"[GameExecutor] 未知消息类型: {mtype}")


def _game_display_name(executor) -> str:
    return str(
        getattr(executor, "game_name", None)
        or getattr(executor, "game_code", None)
        or "未知游戏"
    ).strip()

def _runtime_recovery_pending(executor) -> bool:
    check = getattr(executor, "runtime_recovery_pending", None)
    return bool(check()) if callable(check) else False


async def _probe_connected_games(ctx: AppContext) -> str:
    """总控注册成功后立即检查全部游戏，返回需要语音播报的内容。"""
    alerts: list[str] = []
    for executor in EXECUTOR_REGISTRY.executors():
        probe = getattr(executor, "probe_runtime", None)
        if not callable(probe):
            continue

        game_name = _game_display_name(executor)
        try:
            ready = bool(await asyncio.to_thread(probe))
        except Exception as exc:
            ready = False
            ctx.runtime_status.update(client_status="not_ready", ui_health="unhealthy")
            print(f"[GameExecutor] {game_name}连接后运行态检查异常: {exc}")

        snapshot = ctx.runtime_status.snapshot()
        client_ready = snapshot.get("client_status") == "logged_in"
        ui_health = snapshot.get("ui_health")
        if ready and client_ready and ui_health == "ready":
            print(f"[GameExecutor] {game_name}游戏状态正常")
            continue

        if _runtime_recovery_pending(executor):
            alerts.append(f"{game_name}游戏状态暂未就绪，程序正在自动恢复")
        elif ui_health in {"recoverable", "starting"}:
            alerts.append(f"{game_name}游戏状态暂未就绪，将在收到交易任务后自动恢复")
        else:
            alerts.append(f"{game_name}游戏状态异常，请检查游戏客户端")

    return "。".join(alerts) + ("。" if alerts else "")

async def _retry_pending_game_recovery(client, ctx: AppContext) -> None:
    """注册后仅重试确实已执行过的窗口恢复，不在空闲心跳中持续操作游戏。"""
    pending = [
        executor for executor in EXECUTOR_REGISTRY.executors()
        if _runtime_recovery_pending(executor)
    ]
    if not pending:
        return

    names = "、".join(_game_display_name(executor) for executor in pending)
    print(
        f"[GameExecutor] 已启动连接恢复重试: {names}，"
        f"最多 {CONNECT_RECOVERY_ATTEMPTS} 次，"
        f"间隔 {CONNECT_RECOVERY_INTERVAL_SECONDS:g} 秒"
    )
    for attempt in range(1, CONNECT_RECOVERY_ATTEMPTS + 1):
        await asyncio.sleep(CONNECT_RECOVERY_INTERVAL_SECONDS)
        if ctx.active_trade() is not None:
            print("[GameExecutor] 已收到交易任务，停止连接恢复重试，交由任务流程接管")
            return

        for executor in tuple(pending):
            if not _runtime_recovery_pending(executor):
                pending.remove(executor)
                continue
            game_name = _game_display_name(executor)
            print(
                f"[GameExecutor] {game_name}连接恢复重试 "
                f"{attempt}/{CONNECT_RECOVERY_ATTEMPTS}"
            )
            probe = getattr(executor, "probe_runtime", None)
            try:
                ready = bool(await asyncio.to_thread(probe))
            except Exception as exc:
                ready = False
                ctx.runtime_status.update(
                    client_status="not_ready",
                    ui_health="unhealthy",
                )
                print(f"[GameExecutor] {game_name}连接恢复重试异常: {exc}")
            await _send_runtime_heartbeat(client, ctx)

            if ready:
                pending.remove(executor)
                print(f"[GameExecutor] {game_name}游戏状态已自动恢复")
            elif not _runtime_recovery_pending(executor):
                pending.remove(executor)
                print(
                    f"[GameExecutor] {game_name}窗口已恢复，但尚未进入游戏主界面；"
                    "将在收到交易任务后继续"
                )

        if not pending:
            return

    for executor in pending:
        print(
            f"[GameExecutor] {_game_display_name(executor)}经过 "
            f"{CONNECT_RECOVERY_ATTEMPTS} 次连接恢复重试仍未就绪，"
            "将在收到交易任务后再次尝试"
        )


async def _send_runtime_heartbeat(client, ctx: AppContext) -> None:
    await client.send({
        "type": "heartbeat",
        "runtime": {
            "role": "game_executor",
            **ctx.runtime_status.snapshot(),
        },
    })


# ═══════════════════════════════════════════════════════════
# 连接管理
# ═══════════════════════════════════════════════════════════

async def _heartbeat(client, ctx: AppContext):
    while True:
        await asyncio.sleep(config.HEARTBEAT_INTERVAL)
        # 空闲心跳只上报最近一次状态，不触碰游戏窗口。
        # 窗口恢复/激活仅发生在注册后的单次检查以及收到交易任务后。
        await _send_runtime_heartbeat(client, ctx)


async def _connect_once(ctx: AppContext):
    import websockets

    info = config.get_machine_info()
    info["role"] = "game_executor"
    info["execution_mode"] = "manual_actions" if executor_config.MANUAL_ACTIONS else "live"
    async with websockets.connect(config.BACKEND_WS_URL, max_size=None) as ws:
        loop = asyncio.get_event_loop()
        client = AgentClient(ws, loop)
        reporter = Reporter(client)
        ctx.reporter = reporter

        await client.send({"type": "register", **info})
        print(f"[GameExecutor] 已连接总控，注册中: {info}")

        hb = asyncio.create_task(_heartbeat(client, ctx))
        background_tasks: set[asyncio.Task] = set()
        try:
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except Exception:
                    continue
                if msg.get("type") == "registered":
                    print(f"[GameExecutor] 注册成功 machine_id={msg.get('machine_id')}")
                    alert_text = await _probe_connected_games(ctx)
                    await _send_runtime_heartbeat(client, ctx)
                    if alert_text:
                        task = asyncio.create_task(
                            asyncio.to_thread(speak_text, alert_text),
                            name="game-runtime-voice-alert",
                        )
                        background_tasks.add(task)
                        task.add_done_callback(background_tasks.discard)
                    recovery_task = asyncio.create_task(
                        _retry_pending_game_recovery(client, ctx),
                        name="game-runtime-connect-recovery",
                    )
                    background_tasks.add(recovery_task)
                    recovery_task.add_done_callback(background_tasks.discard)
                    continue
                await _dispatch_message(msg, ctx)
        finally:
            hb.cancel()
            for task in tuple(background_tasks):
                task.cancel()
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
        hardware = _create_hardware_controller()
        if not hardware.connect():
            raise RuntimeError("failed to connect game executor hardware controller")
        executor = LineageClassicExecutor(hardware, runtime_status)
        EXECUTOR_REGISTRY.register(executor)

    while True:
        try:
            await _connect_once(ctx)
        except Exception as e:
            print(f"[GameExecutor] 连接断开/失败: {e}，{config.RECONNECT_INTERVAL}s 后重连")
        await asyncio.sleep(config.RECONNECT_INTERVAL)


def start():
    """启动独立的游戏执行 Worker。"""
    print(f"[GameExecutor] 启动，总控地址: {config.BACKEND_WS_URL}")
    if executor_config.MANUAL_ACTIONS:
        print(
            "[GameExecutor] 人工操作测试模式已启用：订单、识别、等待和终态上报均为真实流程；"
            "程序不会发送 HID；[GAME-ACTION] 会提前显示最终坐标和输入文字，"
            "请按 [MANUAL-ACTION] 指引手动操作游戏"
        )
    asyncio.run(main_loop())


if __name__ == "__main__":
    autostart_result = handle_autostart_args("auto-game-executor")
    if autostart_result is not None:
        sys.exit(autostart_result)
    start()
