import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trader.executor.registry import ExecutorRegistry
from trader.gate import TradeTaskGate


class _Executor:
    game_code = "lineage_classic"

    async def execute(self, order):
        return {"success": True, "message": "ok", "duration_ms": 1}


class TraderCoreTest(unittest.TestCase):
    def test_registry_resolves_game_code_case_insensitively(self):
        registry = ExecutorRegistry()
        executor = _Executor()
        registry.register(executor)

        self.assertIs(executor, registry.get("LINEAGE_CLASSIC"))

    def test_gate_keeps_order_between_offer_and_start(self):
        gate = TradeTaskGate()
        order = {"order_id": 42, "game_code": "lineage_classic"}

        accepted, _ = gate.offer("assignment-1", "token-1", order)

        self.assertTrue(accepted)
        self.assertTrue(gate.start("assignment-1", "token-1"))
        self.assertEqual(order, gate.current_order("assignment-1"))
        self.assertTrue(gate.complete("assignment-1"))
        self.assertIsNone(gate.current_order("assignment-1"))


if __name__ == "__main__":
    unittest.main()
