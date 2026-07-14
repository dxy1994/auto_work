import unittest
from decimal import Decimal

from orders.model import NormalizedOrder


class NormalizedOrderTest(unittest.TestCase):
    def test_wire_payload_uses_stable_protocol_fields(self):
        order = NormalizedOrder(
            platform="itemmania",
            source_order_no="M-100",
            region_external_key="1",
            asset_type="adena",
            asset_amount=Decimal("2500000"),
            buyer_character="구매자",
            platform_status="paid",
            raw_title="아덴01",
        )

        self.assertEqual(order.to_wire(), {
            "platform": "itemmania",
            "source_order_no": "M-100",
            "region_external_key": "1",
            "asset_type": "adena",
            "asset_amount": "2500000",
            "buyer_character": "구매자",
            "platform_status": "paid",
            "raw_title": "아덴01",
        })

    def test_rejects_non_adena_asset_in_first_phase(self):
        with self.assertRaisesRegex(ValueError, "Adena"):
            NormalizedOrder(
                "itembay", "B-1", "1", "item", Decimal("1"),
                "buyer", "paid", "sword")

    def test_rejects_non_positive_amount(self):
        with self.assertRaisesRegex(ValueError, "positive"):
            NormalizedOrder(
                "barotem", "T-1", "1", "adena", Decimal("0"),
                "buyer", "paid", "adena")


if __name__ == "__main__":
    unittest.main()
