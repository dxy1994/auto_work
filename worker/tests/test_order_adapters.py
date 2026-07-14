import json
import unittest
from decimal import Decimal
from pathlib import Path

from orders.adapters import adapter_for, parse_korean_amount


FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name):
    with (FIXTURES / name).open(encoding="utf-8") as stream:
        return json.load(stream)


class OrderAdaptersTest(unittest.TestCase):
    def test_itemmania_paid_adena_row_is_normalized(self):
        order = adapter_for("itemmania").normalize(
            load_fixture("itemmania_order.json"))
        self.assertEqual(order.source_order_no, "M-100")
        self.assertEqual(order.asset_amount, Decimal("2500000"))

    def test_barotem_man_unit_is_normalized(self):
        order = adapter_for("barotem").normalize(
            load_fixture("barotem_order.json"))
        self.assertEqual(order.source_order_no, "T-200")
        self.assertEqual(order.asset_amount, Decimal("2500000"))

    def test_itembay_paid_adena_row_is_normalized(self):
        order = adapter_for("itembay").normalize(
            load_fixture("itembay_order.json"))
        self.assertEqual(order.source_order_no, "B-300")
        self.assertEqual(order.asset_amount, Decimal("2500000"))

    def test_unpaid_row_is_ignored(self):
        raw = load_fixture("itemmania_order.json")
        raw["state"] = "cancelled"
        self.assertIsNone(adapter_for("itemmania").normalize(raw))

    def test_amount_parser_rejects_ambiguous_text(self):
        with self.assertRaises(ValueError):
            parse_korean_amount("2개 x 250만")


if __name__ == "__main__":
    unittest.main()
