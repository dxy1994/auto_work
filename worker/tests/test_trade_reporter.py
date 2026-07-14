import unittest
from decimal import Decimal

from orders.model import NormalizedOrder
from reporter import Reporter


class FakeClient:
    def __init__(self):
        self.messages = []

    def send_threadsafe(self, message):
        self.messages.append(message)


class TradeReporterTest(unittest.TestCase):

    def test_reports_offer_decision_without_execution_token(self):
        client = FakeClient()
        reporter = Reporter(client)

        reporter.report_trade_offer_decision("a-1", True)

        self.assertEqual({
            "type": "trade_offer_decision",
            "assignment_id": "a-1",
            "accepted": True,
            "reason": "",
        }, client.messages[0])

    def test_reports_trade_lifecycle_status(self):
        client = FakeClient()
        reporter = Reporter(client)

        reporter.report_trade_status("a-1", "started", "simulation")

        self.assertEqual({
            "type": "trade_status",
            "assignment_id": "a-1",
            "status": "started",
            "message": "simulation",
        }, client.messages[0])

    def test_reports_normalized_order_without_credentials(self):
        client = FakeClient()
        reporter = Reporter(client)
        order = NormalizedOrder(
            "itembay", "B-300", "1", "adena", Decimal("2500000"),
            "buyer", "paid", "adena")

        reporter.report_order_detected(12, order)

        self.assertEqual({
            "type": "order_detected",
            "account_id": 12,
            "order": order.to_wire(),
        }, client.messages[0])


if __name__ == "__main__":
    unittest.main()
