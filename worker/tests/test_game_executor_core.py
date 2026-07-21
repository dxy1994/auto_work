import os
import sys
import unittest
import asyncio
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game_executor.executor.registry import ExecutorRegistry
from game_executor.gate import TradeTaskGate
from game_executor.main import _dispatch_message
from game_executor.status import RuntimeStatus
from common.context import AppContext


class _Executor:
    game_code = "lineage_classic"
    game_codes = ("lineage_classic", "리니지클래식")

    async def execute(self, order):
        return {"success": True, "message": "ok", "duration_ms": 1}


class GameExecutorCoreTest(unittest.TestCase):
    def test_registry_resolves_game_code_case_insensitively(self):
        registry = ExecutorRegistry()
        executor = _Executor()
        registry.register(executor)

        self.assertIs(executor, registry.get("LINEAGE_CLASSIC"))
        self.assertIs(executor, registry.get("리니지클래식"))

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
