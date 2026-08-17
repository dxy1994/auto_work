import os
import sys
import unittest
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game_executor.executor.registry import ExecutorRegistry
from game_executor.executor.lineage_classic import LineageClassicExecutor
from game_executor.gate import TradeTaskGate
from game_executor.main import (
    _create_hardware_controller,
    _dispatch_message,
    _heartbeat,
    _poll_hardware_binding,
    _probe_connected_games,
    _retry_pending_game_recovery,
    _run_trade_assignment,
    _send_runtime_heartbeat,
    _watch_game_disconnects,
)
from game_executor.hardware_binding import WirelessHidBinding
from game_executor.status import RuntimeStatus
from game_executor.audio import speak_text
from game_executor.executor.lineage_classic.navigation import DisconnectedClient
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

    def test_factory_always_uses_real_wireless_hid_hardware(self):
        binding = WirelessHidBinding(
            record_id=2,
            device_id="AABBCCDDEEFF",
            name="WHID-2",
            host="192.168.1.32",
            port=39667,
        )
        with patch("game_executor.main.HardwareController") as controller_type:
            hardware = _create_hardware_controller(binding)

        self.assertIs(hardware, controller_type.return_value)
        controller_type.assert_called_once_with(
            "192.168.1.32",
            39667,
            expected_device_id="AABBCCDDEEFF",
        )

    def test_registry_resolves_game_code_case_insensitively(self):
        registry = ExecutorRegistry()
        executor = _Executor()
        registry.register(executor)

        self.assertIs(executor, registry.get("LINEAGE_CLASSIC"))
        self.assertIs(executor, registry.get("리니지클래식"))
        self.assertEqual((executor,), registry.executors())

    def test_lineage_executor_uses_canonical_script_name_and_legacy_aliases(self):
        self.assertEqual("lineage_classic", LineageClassicExecutor.game_code)
        self.assertIn("리니지클래식", LineageClassicExecutor.game_codes)
        self.assertIn("天堂经典版", LineageClassicExecutor.game_codes)
        self.assertEqual("天堂经典版", LineageClassicExecutor.game_name)

    def test_registry_can_replace_all_aliases_for_rebound_hardware(self):
        registry = ExecutorRegistry()
        first = _Executor()
        second = _Executor()
        registry.register(first)

        registry.replace(second)

        self.assertIs(second, registry.get("lineage_classic"))
        self.assertIs(second, registry.get("리니지클래식"))
        self.assertEqual((second,), registry.executors())

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


class _BuyerReviewExecutor(_Executor):
    def __init__(self):
        self.decisions = []

    def submit_buyer_review(self, review_id, approved):
        self.decisions.append((review_id, approved))
        return True


class GameExecutorDispatchAsyncTest(unittest.IsolatedAsyncioTestCase):
    async def test_hardware_binding_poll_waits_until_hardware_is_installed(self):
        ctx = AppContext(asyncio.get_running_loop())
        sent = []

        async def send(message):
            sent.append(message)
            if len(sent) == 2:
                ctx.install_hardware(
                    object(),
                    SimpleNamespace(connected=True),
                    object(),
                )

        client = SimpleNamespace(send=send)
        with patch("game_executor.main.HARDWARE_BINDING_POLL_SECONDS", 0):
            await _poll_hardware_binding(client, ctx)

        self.assertEqual(
            [
                {"type": "hardware_binding_request"},
                {"type": "hardware_binding_request"},
            ],
            sent,
        )

    async def test_rejected_buyer_review_is_delivered_to_active_executor(self):
        ctx = AppContext(asyncio.get_running_loop())
        ctx.reporter = _Reporter()
        ctx.runtime_status = RuntimeStatus()
        ctx.trade_task_gate = TradeTaskGate()
        executor = _BuyerReviewExecutor()
        ctx.set_active_trade("assignment-1", executor, None)

        await _dispatch_message({
            "type": "trade_buyer_review_decision",
            "assignment_id": "assignment-1",
            "review_id": "review-1",
            "approved": False,
        }, ctx)

        self.assertEqual([("review-1", False)], executor.decisions)

    async def test_trade_reports_the_real_success_terminal_status(self):
        ctx = AppContext(asyncio.get_running_loop())
        ctx.reporter = _Reporter()
        ctx.runtime_status = RuntimeStatus()
        ctx.trade_task_gate = TradeTaskGate()

        await _run_trade_assignment(
            "assignment-live",
            {"trade_timeout_seconds": 30},
            _Executor(),
            ctx,
        )

        terminal = ctx.reporter.statuses[-1]
        self.assertEqual("completed", terminal[1])

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

    async def test_disconnect_guard_notifies_before_closing_exact_game_pid(self):
        ctx = AppContext(asyncio.get_running_loop())
        ctx.runtime_status = RuntimeStatus()
        ctx.runtime_status.update(game_account_id=19)
        events = []
        closed = asyncio.Event()

        async def send(message):
            events.append(("send", message))

        # terminate() 会在 asyncio.to_thread 中运行，保存主循环供线程安全唤醒。
        loop = asyncio.get_running_loop()

        def terminate_from_thread(process_id):
            events.append(("terminate", process_id))
            loop.call_soon_threadsafe(closed.set)

        window = SimpleNamespace(terminate_process=terminate_from_thread)
        detected = DisconnectedClient(
            window=window,
            process_id=4321,
            account="lineage@example.com",
            confidence=0.973,
            matched_point=(640, 480),
        )
        client = SimpleNamespace(send=send, local_ip="192.168.1.27")

        with patch(
            "game_executor.main.detect_disconnected_client",
            return_value=detected,
        ), patch(
            "game_executor.main.game_executor_config.DISCONNECT_POLL_SECONDS",
            0,
        ), patch(
            "game_executor.main.game_executor_config.DISCONNECT_CONFIRMATIONS",
            2,
        ):
            task = asyncio.create_task(_watch_game_disconnects(client, ctx))
            await asyncio.wait_for(closed.wait(), timeout=1)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task

        self.assertEqual("send", events[0][0])
        self.assertEqual("game_client_disconnected", events[0][1]["type"])
        self.assertEqual(4321, events[0][1]["process_id"])
        self.assertEqual(19, events[0][1]["game_account_id"])
        self.assertEqual(("terminate", 4321), events[1])
        self.assertEqual(
            "disconnected",
            ctx.runtime_status.snapshot()["client_status"],
        )

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
        ctx.install_hardware(
            object(),
            SimpleNamespace(connected=True),
            executor,
        )
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
