import sys
import unittest
from pathlib import Path


WORKER_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKER_ROOT))

from monitor.monitoring.extraction import OrderExtractionResult


class OrderExtractionResultTest(unittest.TestCase):
    def test_normal_empty_table_is_a_successful_result(self):
        result = OrderExtractionResult.success([])

        self.assertFalse(result.failed)
        self.assertEqual([], result.orders)
        self.assertIsNone(result.error)

    def test_extraction_failure_is_not_a_normal_empty_table(self):
        result = OrderExtractionResult.failure("订单表格不存在")

        self.assertTrue(result.failed)
        self.assertEqual([], result.orders)
        self.assertEqual("订单表格不存在", result.error)


if __name__ == "__main__":
    unittest.main()
