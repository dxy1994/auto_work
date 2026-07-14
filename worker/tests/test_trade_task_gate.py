import unittest

from trade.task_gate import TradeTaskGate


class TradeTaskGateTest(unittest.TestCase):

    def test_offer_reserves_one_assignment_and_rejects_second(self):
        gate = TradeTaskGate()

        self.assertEqual((True, "accepted"), gate.offer("a-1", "token-1"))
        self.assertEqual((False, "executor_busy"), gate.offer("a-2", "token-2"))

    def test_repeated_matching_offer_is_idempotent(self):
        gate = TradeTaskGate()
        gate.offer("a-1", "token-1")

        self.assertEqual((True, "accepted"), gate.offer("a-1", "token-1"))

    def test_start_requires_matching_assignment_and_token(self):
        gate = TradeTaskGate()
        gate.offer("a-1", "token-1")

        self.assertFalse(gate.start("a-1", "wrong"))
        self.assertTrue(gate.start("a-1", "token-1"))
        self.assertEqual("running", gate.snapshot()["status"])

    def test_cancel_releases_offer(self):
        gate = TradeTaskGate()
        gate.offer("a-1", "token-1")

        self.assertTrue(gate.cancel("a-1"))
        self.assertEqual("idle", gate.snapshot()["status"])

    def test_completion_only_releases_matching_running_assignment(self):
        gate = TradeTaskGate()
        gate.offer("a-1", "token-1")
        gate.start("a-1", "token-1")

        self.assertFalse(gate.complete("a-2"))
        self.assertTrue(gate.complete("a-1"))
        self.assertEqual("idle", gate.snapshot()["status"])


if __name__ == "__main__":
    unittest.main()
