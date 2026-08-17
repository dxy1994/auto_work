"""游戏执行 Worker 入口：连接总控、注册本机、心跳保活、执行游戏交易指令。

不包含浏览器、订单监控、招呼发送能力。

运行：python -m game_executor.main
"""
import asyncio
import json
import os
import sys
from pathlib import Path
from collections.abc import Mapping

# ── 让 worker 目录内模块可平铺导入 ──
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common import clock
from common import config
from common.context import AppContext
from common.client import AgentClient
from common.protocol import game_client_disconnected_msg
from common.reporter import Reporter
from common.autostart import handle_autostart_args
from game_executor.audio import speak_text
from game_executor import config as game_executor_config
from game_executor.status import RuntimeStatus
from game_executor.gate import TradeTaskGate
from game_executor.executor.registry import EXECUTOR_REGISTRY
from game_executor.executor.hardware.controller import HardwareController
from game_executor.executor.lineage_classic import LineageClassicExecutor
from game_executor.executor.lineage_classic.navigation import (
    NavigationError,
    detect_disconnected_client,
)
from game_executor.executor.lineage_classic.policy import execution_timeout_seconds
from game_executor.hardware_binding import WirelessHidBinding

# 安装时间戳 print
clock.install()


def run_self_check() -> int:
    """Validate packaged game dependencies and recognition assets without hardware."""
    import importlib
    import platform

    required_modules = (
        "websockets",
        "dotenv",
        "cv2",
        "numpy",
        "PIL",
        "paddle",
        "paddleocr",
        "paddlex",
        "boto3",
        "pythoncom",
        "win32api",
        "win32gui",
        "win32com.client",
        "game_executor.executor.hardware.whid_sdk",
        "game_executor.executor.lineage_classic.navigation",
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
        from game_executor.executor.lineage_classic import navigation

        image_directory = Path(navigation.__file__).with_name("images")
        recognition_images = tuple(image_directory.glob("*.png"))
        if not image_directory.is_dir() or not recognition_images:
            raise RuntimeError(f"recognition images missing: {image_directory}")
        print(
            f"[SelfCheck][OK] recognition assets: "
            f"{len(recognition_images)} file(s) in {image_directory}"
        )
    except Exception as exc:
        failures.append(f"recognition assets: {exc}")
        print(f"[SelfCheck][FAILED] recognition assets: {exc}")

    format_ocr_error = str
    try:
        from game_executor.executor.lineage_classic.paddle_ocr import (
            build_paddle_ocr_engine,
            build_text_recognition_engine,
            bundled_ocr_model_directories,
            exception_chain_message,
        )
        format_ocr_error = exception_chain_message

        model_directories = bundled_ocr_model_directories()
        if getattr(sys, "frozen", False) and not model_directories:
            raise RuntimeError("packaged OCR model directory was not selected")
        print(
            "[SelfCheck][OK] bundled OCR models: "
            + ", ".join(sorted(model_directories))
        )

        # Importing PaddleOCR is insufficient: PaddleX validates distribution
        # metadata only while constructing each predictor. Exercise the exact
        # engines used by trades so a broken frozen package cannot be deployed.
        build_paddle_ocr_engine()
        build_text_recognition_engine("english")
        build_text_recognition_engine("korean")
        print("[SelfCheck][OK] OCR predictors: full, english, korean")
    except Exception as exc:
        detail = format_ocr_error(exc)
        failures.append(f"OCR runtime: {detail}")
        print(f"[SelfCheck][FAILED] OCR runtime: {detail}")

    print(
        f"[SelfCheck] Python={platform.python_version()} "
        f"architecture={platform.architecture()[0]} frozen={getattr(sys, 'frozen', False)}"
    )
    if failures:
        print(f"[SelfCheck] Game Executor package failed with {len(failures)} problem(s).")
        return 1
    print("[SelfCheck] Game Executor package is ready.")
    return 0


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
HARDWARE_BINDING_POLL_SECONDS = 3.0


def _create_hardware_controller(binding: WirelessHidBinding):
    return HardwareController(
        binding.host,
        binding.port,
        expected_device_id=binding.device_id,
    )


def _clear_hardware_controller(ctx: AppContext) -> None:
    previous = ctx.clear_hardware()
    executor = previous.get("executor")
    if executor is not None:
        EXECUTOR_REGISTRY.unregister(executor)
    hardware = previous.get("hardware")
    if hardware is not None:
        hardware.disconnect()


def _configure_hardware_binding(payload, ctx: AppContext) -> bool:
    """Install the exact HID assigned by the controller.

    Returns True when a new controller was installed and False when the current
    verified controller already matches the binding.
    """
    binding = WirelessHidBinding.from_payload(payload)
    current = ctx.hardware_snapshot()
    current_hardware = current.get("hardware")
    if current.get("binding") == binding and bool(
        current_hardware is not None and current_hardware.connected
    ):
        return False
    if ctx.active_trade() is not None:
        raise RuntimeError("cannot switch Wireless HID during an active trade")

    _clear_hardware_controller(ctx)
    hardware = _create_hardware_controller(binding)
    if not hardware.connect():
        feedback = hardware.last_feedback or {}
        raise RuntimeError(
            str(feedback.get("error") or "Wireless HID connection failed")
        )

    try:
        executor = LineageClassicExecutor(hardware, ctx.runtime_status)
    except Exception:
        hardware.disconnect()
        raise
    EXECUTOR_REGISTRY.replace(executor)
    ctx.install_hardware(binding, hardware, executor)
    ctx.runtime_status.update(executor_status="idle")
    print(
        "[GameExecutor][HID] 已关联并校验键鼠设备 "
        f"record_id={binding.record_id} device_id={binding.device_id} "
        f"address={binding.host}:{binding.port}",
        flush=True,
    )
    return True


async def _try_configure_hardware(message, ctx: AppContext) -> bool:
    payload = message.get("wireless_hid")
    if not isinstance(payload, Mapping):
        if ctx.active_trade() is None:
            await asyncio.to_thread(_clear_hardware_controller, ctx)
        ctx.runtime_status.update(
            client_status="not_ready",
            executor_status="waiting_hardware",
            ui_health="unhealthy",
        )
        error = message.get("hardware_error") or "当前机器尚未绑定键鼠设备"
        print(f"[GameExecutor][HID] 等待键鼠设备绑定: {error}", flush=True)
        return False
    try:
        await asyncio.to_thread(_configure_hardware_binding, payload, ctx)
        return True
    except Exception as exc:
        ctx.runtime_status.update(
            client_status="not_ready",
            executor_status="waiting_hardware",
            ui_health="unhealthy",
        )
        print(f"[GameExecutor][HID] 绑定设备尚未就绪，将继续轮询: {exc}", flush=True)
        return False


async def _poll_hardware_binding(client, ctx: AppContext) -> None:
    """Keep the registered worker online until a verified HID is available."""
    while True:
        snapshot = ctx.hardware_snapshot()
        hardware = snapshot.get("hardware")
        if hardware is not None and hardware.connected:
            return
        await client.send({"type": "hardware_binding_request"})
        await asyncio.sleep(HARDWARE_BINDING_POLL_SECONDS)


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
        def report_buyer_review(review):
            from game_executor import storage as game_storage

            payload = dict(review or {})
            screenshot = payload.pop("screenshot_data_url", "")
            try:
                screenshot_path = game_storage.upload_trade_screenshot(
                    f"{assignment_id}-buyer-review",
                    screenshot,
                )
                payload["screenshot_path"] = screenshot_path
                print(
                    f"[GameExecutor][BuyerReview] assignment_id={assignment_id} "
                    f"审核截图已直传 RustFS path={screenshot_path}",
                    flush=True,
                )
            except Exception as exc:
                # 图片存储异常时仍上报人工审核，避免交易线程在无人可见的状态下等待。
                payload["screenshot_data_url"] = screenshot
                print(
                    f"[GameExecutor][BuyerReview] assignment_id={assignment_id} "
                    f"审核截图上传 RustFS 失败，将仅保留中控人工审核: {exc}",
                    flush=True,
                )
            reporter.report_trade_buyer_review(assignment_id, payload)

        set_buyer_review(report_buyer_review)
    set_trade_screenshot = getattr(executor, "set_trade_screenshot_callback", None)
    if callable(set_trade_screenshot):
        def confirm_final_trade(screenshot):
            from game_executor import storage as game_storage

            try:
                screenshot_path = game_storage.upload_trade_screenshot(
                    assignment_id, screenshot
                )
            except Exception as exc:
                print(
                    f"[GameExecutor][Trade] assignment_id={assignment_id} "
                    f"交易截图上传 RustFS 失败: {exc}",
                    flush=True,
                )
                return {
                    "approved": False,
                    "reply_received": False,
                    "error": f"交易截图上传失败: {exc}",
                }
            print(
                f"[GameExecutor][Trade] assignment_id={assignment_id} "
                f"交易截图已直传 RustFS path={screenshot_path}",
                flush=True,
            )
            return reporter.request_trade_final_confirmation(
                assignment_id, screenshot_path
            )

        set_trade_screenshot(
            confirm_final_trade
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
        if "wireless_hid" in msg and not await _try_configure_hardware(msg, ctx):
            reporter.report_trade_offer_decision(
                assignment_id,
                False,
                "hardware_binding_not_ready",
            )
            return
        hardware = ctx.hardware_snapshot().get("hardware")
        if hardware is None or not hardware.connected:
            reporter.report_trade_offer_decision(
                assignment_id,
                False,
                "hardware_not_ready",
            )
            return
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
        review_id = msg.get("review_id")
        approved = bool(msg.get("approved"))
        print(
            f"[GameExecutor][BuyerReview] 收到总控决定 "
            f"assignment_id={assignment_id} review_id={review_id} "
            f"decision={'approved' if approved else 'rejected'}",
            flush=True,
        )
        active = ctx.active_trade(assignment_id)
        submit_review = (
            getattr(active["executor"], "submit_buyer_review", None)
            if active is not None else None
        )
        accepted = callable(submit_review) and submit_review(review_id, approved)
        if accepted:
            print(
                f"[GameExecutor][BuyerReview] 审核决定已交给交易执行线程 "
                f"assignment_id={assignment_id} review_id={review_id}",
                flush=True,
            )
        else:
            print(
                f"[GameExecutor][BuyerReview] 忽略已失效的买家审核决定: "
                f"assignment_id={assignment_id} review_id={review_id} "
                f"active_assignment_id="
                f"{active.get('assignment_id') if active is not None else None}",
                flush=True,
            )

    elif mtype == "trade_game_screenshot_saved":
        reporter.deliver_trade_game_screenshot_saved(
            msg.get("request_id"), bool(msg.get("success")))

    elif mtype == "trade_final_confirmation_result":
        reporter.deliver_trade_final_confirmation_result(
            msg.get("request_id"),
            {
                "approved": bool(msg.get("approved")),
                "reply_received": bool(msg.get("reply_received")),
                "reply_text": str(msg.get("reply_text") or ""),
                "error_code": str(msg.get("error_code") or ""),
                "error": str(msg.get("error") or ""),
            },
        )

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
        "ip": config.get_machine_ip(getattr(client, "local_ip", None)),
        "runtime": {
            "role": "game_executor",
            **ctx.runtime_status.snapshot(),
        },
    })


async def _watch_game_disconnects(client, ctx: AppContext) -> None:
    """连续确认断线弹窗；先通知总控，再关闭命中窗口所属游戏进程。"""
    candidate_pid = None
    consecutive_hits = 0
    notified_pids: set[int] = set()
    closed_pids: set[int] = set()
    last_probe_error = ""

    while True:
        await asyncio.sleep(game_executor_config.DISCONNECT_POLL_SECONDS)
        try:
            detected = await asyncio.to_thread(detect_disconnected_client)
            last_probe_error = ""
        except NavigationError as exc:
            detected = None
            error = str(exc)
            if error != last_probe_error and "未找到 Lineage Classic" not in error:
                print(f"[GameExecutor][掉线检测] 本轮无法检查: {error}", flush=True)
            last_probe_error = error
        except Exception as exc:
            detected = None
            error = str(exc)
            if error != last_probe_error:
                print(f"[GameExecutor][掉线检测] 检查异常: {error}", flush=True)
            last_probe_error = error

        if detected is None:
            candidate_pid = None
            consecutive_hits = 0
            continue

        process_id = detected.process_id
        if process_id in closed_pids:
            continue
        if candidate_pid == process_id:
            consecutive_hits += 1
        else:
            candidate_pid = process_id
            consecutive_hits = 1
        if consecutive_hits < game_executor_config.DISCONNECT_CONFIRMATIONS:
            print(
                "[GameExecutor][掉线检测] 候选画面待复核 "
                f"pid={process_id} hits={consecutive_hits}/"
                f"{game_executor_config.DISCONNECT_CONFIRMATIONS}",
                flush=True,
            )
            continue

        snapshot = ctx.runtime_status.snapshot()
        ctx.runtime_status.update(
            client_status="disconnected",
            ui_health="unhealthy",
        )
        if process_id not in notified_pids:
            notification = game_client_disconnected_msg(
                game_code="lineage_classic",
                game_name="天堂经典版",
                account=detected.account,
                game_account_id=snapshot.get("game_account_id"),
                process_id=process_id,
                confidence=detected.confidence,
            )
            try:
                await client.send(notification)
            except Exception as exc:
                print(
                    "[GameExecutor][掉线检测] 通知总控失败，暂不关闭游戏，"
                    f"下轮重试: {exc}",
                    flush=True,
                )
                continue
            notified_pids.add(process_id)
            print(
                "[GameExecutor][掉线检测] 已通知总控，准备关闭游戏进程 "
                f"pid={process_id}",
                flush=True,
            )

        active = ctx.active_trade()
        if active is not None:
            active["executor"].cancel()
        try:
            await asyncio.to_thread(
                detected.window.terminate_process,
                process_id,
            )
        except Exception as exc:
            print(
                f"[GameExecutor][掉线检测] 关闭游戏进程失败 pid={process_id}: {exc}",
                flush=True,
            )
            continue
        closed_pids.add(process_id)
        print(
            f"[GameExecutor][掉线检测] 游戏进程已关闭 pid={process_id}",
            flush=True,
        )
        await _send_runtime_heartbeat(client, ctx)


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

    async with websockets.connect(config.BACKEND_WS_URL, max_size=None) as ws:
        loop = asyncio.get_event_loop()
        client = AgentClient(ws, loop)
        info = config.get_machine_info(client.local_ip)
        info["role"] = "game_executor"
        info["execution_mode"] = "live"
        reporter = Reporter(client)
        ctx.reporter = reporter

        await client.send({"type": "register", **info})
        print(f"[GameExecutor] 已连接总控，注册中: {info}")

        hb = asyncio.create_task(_heartbeat(client, ctx))
        background_tasks: set[asyncio.Task] = set()
        binding_poll_task = None
        disconnect_watch_task = None
        hardware_runtime_started = False
        try:
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except Exception:
                    continue
                if msg.get("type") in {"registered", "hardware_binding"}:
                    is_registration = msg.get("type") == "registered"
                    if is_registration:
                        print(
                            f"[GameExecutor] 注册成功 machine_id={msg.get('machine_id')}"
                        )
                        if (
                            disconnect_watch_task is None
                            or disconnect_watch_task.done()
                        ):
                            disconnect_watch_task = asyncio.create_task(
                                _watch_game_disconnects(client, ctx),
                                name="game-disconnect-watch",
                            )
                            background_tasks.add(disconnect_watch_task)
                            disconnect_watch_task.add_done_callback(
                                background_tasks.discard
                            )
                    hardware_ready = await _try_configure_hardware(msg, ctx)
                    if not hardware_ready:
                        await _send_runtime_heartbeat(client, ctx)
                        if binding_poll_task is None or binding_poll_task.done():
                            binding_poll_task = asyncio.create_task(
                                _poll_hardware_binding(client, ctx),
                                name="wireless-hid-binding-poll",
                            )
                            background_tasks.add(binding_poll_task)
                            binding_poll_task.add_done_callback(background_tasks.discard)
                        continue

                    if binding_poll_task is not None and not binding_poll_task.done():
                        binding_poll_task.cancel()
                    if hardware_runtime_started:
                        await _send_runtime_heartbeat(client, ctx)
                        continue

                    hardware_runtime_started = True
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
    runtime_status.update(
        client_status="not_ready",
        executor_status="waiting_hardware",
        ui_health="unhealthy",
    )

    try:
        while True:
            try:
                await _connect_once(ctx)
            except Exception as e:
                print(f"[GameExecutor] 连接断开/失败: {e}，{config.RECONNECT_INTERVAL}s 后重连")
            await asyncio.sleep(config.RECONNECT_INTERVAL)
    finally:
        await asyncio.to_thread(_clear_hardware_controller, ctx)


def start():
    """启动独立的游戏执行 Worker。"""
    print(f"[GameExecutor] 启动，总控地址: {config.BACKEND_WS_URL}")
    asyncio.run(main_loop())


if __name__ == "__main__":
    if "--self-check" in sys.argv:
        sys.exit(run_self_check())
    autostart_result = handle_autostart_args("auto-game-executor")
    if autostart_result is not None:
        sys.exit(autostart_result)
    start()
