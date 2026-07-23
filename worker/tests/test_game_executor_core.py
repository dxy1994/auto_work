import os
import sys
import unittest
import asyncio
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game_executor.executor.registry import ExecutorRegistry
from game_executor.gate import TradeTaskGate
from game_executor.executor.hardware.manual import ManualActionHardwareController
from game_executor.main import (
    _create_hardware_controller,
    _dispatch_message,
    _heartbeat,
    _probe_connected_games,
    _retry_pending_game_recovery,
    _run_trade_assignment,
    _send_runtime_heartbeat,
)
from game_executor.status import RuntimeStatus
from game_executor.audio import speak_text
from common.context import AppContext


class _Executor:
    game_code = "lineage_classic"
    game_codes = ("lineage_classic", "리니지클래식")
    game_name = "天堂经典版"

    async def execute(self, order):
        return {"success": True, "message": "ok", "duration_ms": 1}


class _RuntimeProbeExecutor(_Executor):
    def __init__(
        self,
        runtime,
        ready=False,
        ui_health="unhealthy",
        recovery_pending=False,
    ):
        self.runtime = runtime
        self.ready = ready
        self.ui_health = ui_health
        self.recovery_pending = recovery_pending
        self.probe_calls = 0

    def probe_runtime(self):
        self.probe_calls += 1
        self.runtime.update(
            client_status="logged_in" if self.ready else "not_ready",
            ui_health=self.ui_health,
        )
        return self.ready

    def runtime_recovery_pending(self):
        return self.recovery_pending


class GameExecutorCoreTest(unittest.TestCase):
    def test_voice_prefers_powershell_system_speech(self):
        with patch(
            "game_executor.audio._speak_with_powershell"
        ) as powershell, patch(
            "game_executor.audio._speak_with_sapi"
        ) as sapi:
            success = speak_text("天堂经典版游戏状态异常")

        self.assertTrue(success)
        powershell.assert_called_once_with("天堂经典版游戏状态异常")
        sapi.assert_not_called()

    def test_voice_falls_back_to_sapi_when_system_speech_is_unavailable(self):
        with patch(
            "game_executor.audio._speak_with_powershell",
            side_effect=RuntimeError("System.Speech unavailable"),
        ), patch("game_executor.audio._speak_with_sapi") as sapi:
            success = speak_text("天堂经典版游戏状态异常")

        self.assertTrue(success)
        sapi.assert_called_once_with("天堂经典版游戏状态异常")

    def test_manual_mode_uses_log_only_hardware_with_action_coordinates(self):
        with patch("game_executor.main.executor_config.MANUAL_ACTIONS", True), patch(
            "game_executor.main.executor_config.MANUAL_ACTION_WAIT_SECONDS", 0
        ):
            hardware = _create_hardware_controller()

        self.assertIsInstance(hardware, ManualActionHardwareController)
        self.assertTrue(hardware.mouse_move(100, 200))
        self.assertTrue(hardware.mouse_click())
        self.assertEqual(1, hardware.planned_actions)
        self.assertEqual(0, hardware.health_check()["hid_commands_sent"])

    def test_registry_resolves_game_code_case_insensitively(self):
        registry = ExecutorRegistry()
        executor = _Executor()
        registry.register(executor)

        self.assertIs(executor, registry.get("LINEAGE_CLASSIC"))
        self.assertIs(executor, registry.get("리니지클래식"))
        self.assertEqual((executor,), registry.executors())

    def test_gate_keeps_order_between_offer_and_start(self):
        gate = TradeTaskGate()
        order = {"order_id": 42, "game_code": "lineage_classic"}

        accepted, _ = gate.offer("assignment-1", "token-1", order)

        self.assertTrue(accepted)
        self.assertTrue(gate.start("assignment-1", "token-1"))
        self.assertEqual(order, gate.current_order("assignment-1"))
        self.assertTrue(gate.complete("assignment-1"))
        self.assertIsNone(gate.current_order("assignment-1"))


class _Reporter:
    def __init__(self):
        self.decisions = []
        self.statuses = []

    def report_trade_offer_decision(self, *args):
        self.decisions.append(args)

    def report_trade_status(self, *args):
        self.statuses.append(args)


class _CancellableExecutor(_Executor):
    def __init__(self):
        self.started = asyncio.Event()
        self.cancelled = asyncio.Event()
        self.cancel_calls = 0
        self.progress = None

    def set_progress_callback(self, callback):
        self.progress = callback

    async def execute(self, order):
        self.started.set()
        await self.cancelled.wait()
        return {
            "success": False,
            "status": "cancelled",
            "error_code": "TRADE_CANCELLED",
            "message": "cancelled",
        }

    def cancel(self):
        self.cancel_calls += 1
        self.cancelled.set()


class GameExecutorDispatchAsyncTest(unittest.IsolatedAsyncioTestCase):
    async def test_manual_mode_reports_the_real_success_terminal_status(self):
        ctx = AppContext(asyncio.get_running_loop())
        ctx.reporter = _Reporter()
        ctx.runtime_status = RuntimeStatus()
        ctx.trade_task_gate = TradeTaskGate()

        with patch("game_executor.main.executor_config.MANUAL_ACTIONS", True):
            await _run_trade_assignment(
                "assignment-manual",
                {"trade_timeout_seconds": 30},
                _Executor(),
                ctx,
            )

        terminal = ctx.reporter.statuses[-1]
        self.assertEqual("completed", terminal[1])
        self.assertNotIn("DRY_RUN_NO_HID", terminal)

    async def test_connected_probe_names_unhealthy_game_and_reports_immediately(self):
        registry = ExecutorRegistry()
        ctx = AppContext(asyncio.get_running_loop())
        ctx.runtime_status = RuntimeStatus()
        executor = _RuntimeProbeExecutor(ctx.runtime_status)
        registry.register(executor)
        client = type("Client", (), {"send": AsyncMock()})()

        with patch("game_executor.main.EXECUTOR_REGISTRY", registry):
            alert = await _probe_connected_games(ctx)
            await _send_runtime_heartbeat(client, ctx)

        self.assertEqual(1, executor.probe_calls)
        self.assertIn("天堂经典版游戏状态异常", alert)
        sent = client.send.await_args.args[0]
        self.assertEqual("heartbeat", sent["type"])
        self.assertEqual("unhealthy", sent["runtime"]["ui_health"])

    async def test_connected_probe_does_not_announce_healthy_game(self):
        registry = ExecutorRegistry()
        ctx = AppContext(asyncio.get_running_loop())
        ctx.runtime_status = RuntimeStatus()
        executor = _RuntimeProbeExecutor(ctx.runtime_status, ready=True, ui_health="ready")
        registry.register(executor)

        with patch("game_executor.main.EXECUTOR_REGISTRY", registry):
            alert = await _probe_connected_games(ctx)

        self.assertEqual("", alert)

    async def test_connected_probe_only_says_recovering_when_recovery_is_pending(self):
        registry = ExecutorRegistry()
        ctx = AppContext(asyncio.get_running_loop())
        ctx.runtime_status = RuntimeStatus()
        executor = _RuntimeProbeExecutor(
            ctx.runtime_status,
            ui_health="recoverable",
            recovery_pending=False,
        )
        registry.register(executor)

        with patch("game_executor.main.EXECUTOR_REGISTRY", registry):
            alert = await _probe_connected_games(ctx)

        self.assertIn("将在收到交易任务后自动恢复", alert)
        self.assertNotIn("程序正在自动恢复", alert)

        executor.recovery_pending = True
        with patch("game_executor.main.EXECUTOR_REGISTRY", registry):
            alert = await _probe_connected_games(ctx)

        self.assertIn("程序正在自动恢复", alert)

    async def test_connect_recovery_retries_pending_window_and_reports_success(self):
        registry = ExecutorRegistry()
        ctx = AppContext(asyncio.get_running_loop())
        ctx.runtime_status = RuntimeStatus()
        executor = _RuntimeProbeExecutor(
            ctx.runtime_status,
            ui_health="recoverable",
            recovery_pending=True,
        )

        def recover():
            executor.probe_calls += 1
            executor.ready = True
            executor.ui_health = "ready"
            executor.recovery_pending = False
            ctx.runtime_status.update(client_status="logged_in", ui_health="ready")
            return True

        executor.probe_runtime = recover
        registry.register(executor)
        client = type("Client", (), {"send": AsyncMock()})()

        with patch("game_executor.main.EXECUTOR_REGISTRY", registry), patch(
            "game_executor.main.CONNECT_RECOVERY_INTERVAL_SECONDS", 0
        ):
            await _retry_pending_game_recovery(client, ctx)

        self.assertEqual(1, executor.probe_calls)
        client.send.assert_awaited()
        self.assertEqual("ready", ctx.runtime_status.snapshot()["ui_health"])

    async def test_idle_heartbeat_reports_cached_status_without_probing_window(self):
        registry = ExecutorRegistry()
        ctx = AppContext(asyncio.get_running_loop())
        ctx.runtime_status = RuntimeStatus()
        executor = _RuntimeProbeExecutor(ctx.runtime_status, ready=True, ui_health="ready")
        registry.register(executor)
        sent = asyncio.Event()

        async def send(_message):
            sent.set()

        client = type("Client", (), {"send": AsyncMock(side_effect=send)})()
        with patch("game_executor.main.EXECUTOR_REGISTRY", registry), patch(
            "game_executor.main.config.HEARTBEAT_INTERVAL", 0
        ):
            task = asyncio.create_task(_heartbeat(client, ctx))
            await asyncio.wait_for(sent.wait(), timeout=0.1)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task

        self.assertEqual(0, executor.probe_calls)
        self.assertGreaterEqual(client.send.await_count, 1)

    async def test_start_does_not_block_receive_loop_and_cancel_reaches_executor(self):
        registry = ExecutorRegistry()
        executor = _CancellableExecutor()
        registry.register(executor)

        ctx = AppContext(asyncio.get_running_loop())
        ctx.reporter = _Reporter()
        ctx.runtime_status = RuntimeStatus()
        ctx.trade_task_gate = TradeTaskGate()
        order = {"order_id": 42, "game_code": "lineage_classic", "trade_timeout_seconds": 30}

        with patch("game_executor.main.EXECUTOR_REGISTRY", registry):
            await _dispatch_message({
                "type": "trade_offer",
                "assignment_id": "assignment-1",
                "execution_token": "token-1",
                "order": order,
            }, ctx)
            await asyncio.wait_for(_dispatch_message({
                "type": "trade_start",
                "assignment_id": "assignment-1",
                "execution_token": "token-1",
            }, ctx), timeout=0.1)
            await asyncio.wait_for(executor.started.wait(), timeout=0.1)

            active = ctx.active_trade("assignment-1")
            self.assertIsNotNone(active)
            self.assertFalse(active["task"].done())

            await _dispatch_message({
                "type": "trade_cancel",
                "assignment_id": "assignment-1",
            }, ctx)
            await asyncio.wait_for(active["task"], timeout=0.2)

        self.assertEqual(1, executor.cancel_calls)
        self.assertEqual("idle", ctx.trade_task_gate.snapshot()["status"])
        self.assertTrue(any(row[1] == "cancelled" for row in ctx.reporter.statuses))


if __name__ == "__main__":
    unittest.main()
