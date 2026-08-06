import asyncio
import inspect
import sys
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock


WORKER_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKER_ROOT))

from common.protocol import sales_products_snapshot_msg  # noqa: E402
from common.reporter import Reporter  # noqa: E402
from monitor.monitoring.platforms.barotem import (  # noqa: E402
    _parse_sales_product_card_payload as parse_barotem_product,
)
from monitor.monitoring.platforms.itemmania import (  # noqa: E402
    ManiaRefreshWorker,
    _parse_sales_product_row_payload as parse_mania_product,
)
from monitor.monitoring.platforms.itembay import (  # noqa: E402
    ItembayRefreshWorker,
    _parse_sales_product_row_payload as parse_bay_product,
)


class _AckClient:
    def __init__(self):
        self.reporter = None
        self.sent = None

    def send_threadsafe(self, message):
        self.sent = message

        def acknowledge():
            self.reporter.deliver_sales_products_snapshot_result(
                message["request_id"],
                {
                    "success": True,
                    "received_count": len(
                        message["snapshot"]["products"]),
                    "inserted_count": 1,
                    "updated_count": 0,
                    "unchanged_count": 0,
                    "deleted_count": 2,
                },
            )

        threading.Timer(0.01, acknowledge).start()


class _FakeSession:
    account_id = 9

    @staticmethod
    def is_login_page(_url):
        return False


class SalesProductProtocolTest(unittest.TestCase):
    def test_snapshot_message_contains_complete_product_list(self):
        message = sales_products_snapshot_msg(
            9,
            "barotem",
            [{"platform_product_id": "39182563"}],
            "request-1",
        )

        self.assertEqual("sales_products_snapshot", message["type"])
        self.assertEqual(9, message["account_id"])
        self.assertEqual("barotem", message["snapshot"]["platform"])
        self.assertEqual(
            "39182563",
            message["snapshot"]["products"][0]["platform_product_id"],
        )

    def test_reporter_waits_for_database_sync_ack(self):
        client = _AckClient()
        reporter = Reporter(client)
        client.reporter = reporter

        result = reporter.sync_sales_products_snapshot(
            9,
            "barotem",
            [{"platform_product_id": "39182563"}],
            timeout=1,
        )

        self.assertTrue(result["success"])
        self.assertEqual(2, result["deleted_count"])
        self.assertEqual(
            "sales_products_snapshot",
            client.sent["type"],
        )

    def test_three_platform_live_row_shapes_are_normalized(self):
        barotem = parse_barotem_product({
            "platform_product_id": "39182563",
            "game_name": "아이온2",
            "region_name": "월드 거래소(마족) /",
            "title": "빠른 %키나% 거래",
            "quantity_text": "99억 키나",
            "price_text": "5,080 원",
            "platform_registered_at": "26년 07월 31일 12:52:43",
        }, "money")
        mania = parse_mania_product({
            "platform_product_id": "2026073009945700",
            "platform_item_type": "아이템",
            "game_name": "리니지클래식",
            "region_name": "린델",
            "title": "뇌신검 팝니다.",
            "quantity_text": "",
            "price_text": "1,600,000원",
            "platform_registered_at": "07-31 14:49",
        })
        bay = parse_bay_product({
            "platform_product_id": "33572289620",
            "platform_item_type": "아이템",
            "game_region": "디아블로2:레저렉션 - 래더",
            "title": "무공룬셋",
            "quantity_text": "최소 1 최대 43",
            "price_text": "1당 18,400원",
            "platform_registered_at": "07/31 13:30",
        })

        self.assertEqual("39182563", barotem["platform_product_id"])
        self.assertEqual(
            "월드 거래소(마족)", barotem["region_name"])
        self.assertEqual(
            "2026073009945700", mania["platform_product_id"])
        self.assertEqual(
            "디아블로2:레저렉션", bay["game_name"])
        self.assertEqual("래더", bay["region_name"])


class StableSnapshotTest(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _worker_page(snapshot):
        locator = SimpleNamespace(
            evaluate_all=AsyncMock(return_value=snapshot))
        return SimpleNamespace(
            locator=MagicMock(return_value=locator))

    async def test_itemmania_rejects_missing_rows_instead_of_empty_snapshot(
            self):
        worker = ManiaRefreshWorker(
            _FakeSession(), None,
            SimpleNamespace(reporter=None, account_id=9))
        worker._page = self._worker_page({
            "total_rows": 0,
            "empty_rows": 0,
            "products": [],
        })

        with self.assertRaisesRegex(RuntimeError, "停止同步以避免误删"):
            await worker._extract_sales_products_page()

    async def test_itemmania_accepts_explicit_empty_state(self):
        worker = ManiaRefreshWorker(
            _FakeSession(), None,
            SimpleNamespace(reporter=None, account_id=9))
        worker._page = self._worker_page({
            "total_rows": 1,
            "empty_rows": 1,
            "products": [],
        })

        self.assertEqual(
            [], await worker._extract_sales_products_page())

    async def test_itemmania_excludes_recognized_hidden_rows(self):
        worker = ManiaRefreshWorker(
            _FakeSession(), None,
            SimpleNamespace(reporter=None, account_id=9))
        worker._page = self._worker_page({
            "total_rows": 2,
            "empty_rows": 0,
            "inactive_rows": 2,
            "products": [],
        })

        self.assertEqual(
            [], await worker._extract_sales_products_page())

    async def test_itembay_rejects_unrecognized_empty_state(self):
        worker = ItembayRefreshWorker(
            _FakeSession(), None,
            SimpleNamespace(reporter=None, account_id=9))
        worker._page = self._worker_page({
            "total_rows": 1,
            "empty_rows": 0,
            "products": [],
        })

        with self.assertRaisesRegex(RuntimeError, "停止同步以避免误删"):
            await worker._extract_sales_products_page()

    async def test_itembay_accepts_explicit_empty_state(self):
        worker = ItembayRefreshWorker(
            _FakeSession(), None,
            SimpleNamespace(reporter=None, account_id=9))
        worker._page = self._worker_page({
            "total_rows": 1,
            "empty_rows": 1,
            "products": [],
        })

        self.assertEqual(
            [], await worker._extract_sales_products_page())

    async def test_itembay_excludes_recognized_hidden_rows(self):
        worker = ItembayRefreshWorker(
            _FakeSession(), None,
            SimpleNamespace(reporter=None, account_id=9))
        worker._page = self._worker_page({
            "total_rows": 1,
            "empty_rows": 0,
            "inactive_rows": 1,
            "products": [],
        })

        self.assertEqual(
            [], await worker._extract_sales_products_page())

    def test_marketplace_extractors_keep_only_active_listings(self):
        mania_source = inspect.getsource(
            ManiaRefreshWorker._extract_sales_products_page)
        bay_source = inspect.getsource(
            ItembayRefreshWorker._extract_sales_products_page)
        from monitor.monitoring.platforms.barotem import BarotemRefreshWorker
        barotem_source = inspect.getsource(
            BarotemRefreshWorker._extract_sales_products_page)

        self.assertIn(".list_icon.hide", mania_source)
        self.assertIn('a[title="수정"]', bay_source)
        self.assertIn("classList.contains('on')", barotem_source)

    async def test_itemmania_does_not_report_unstable_snapshot(self):
        reporter = SimpleNamespace(
            sync_sales_products_snapshot=MagicMock())
        monitor = SimpleNamespace(
            reporter=reporter,
            account_id=9,
        )
        worker = ManiaRefreshWorker(_FakeSession(), None, monitor)
        worker._crawl_sales_products_once = AsyncMock(side_effect=[
            {"1": {"platform_product_id": "1"}},
            {"2": {"platform_product_id": "2"}},
        ])

        with self.assertRaisesRegex(RuntimeError, "两次商品列表快照不一致"):
            await worker._sync_sales_products(10000)

        reporter.sync_sales_products_snapshot.assert_not_called()

    async def test_itembay_reports_only_after_two_equal_snapshots(self):
        product = {
            "platform_product_id": "33572289620",
            "title": "商品",
        }
        reporter = SimpleNamespace(
            sync_sales_products_snapshot=MagicMock(return_value={
                "success": True,
                "received_count": 1,
                "inserted_count": 0,
                "updated_count": 0,
                "unchanged_count": 1,
                "deleted_count": 0,
            }))
        monitor = SimpleNamespace(
            reporter=reporter,
            account_id=9,
        )
        worker = ItembayRefreshWorker(_FakeSession(), None, monitor)
        worker._crawl_sales_products_once = AsyncMock(side_effect=[
            {"33572289620": product},
            {"33572289620": dict(product)},
        ])

        result = await worker._sync_sales_products(10000)

        self.assertTrue(result["success"])
        reporter.sync_sales_products_snapshot.assert_called_once_with(
            9, "itembay", [product])


if __name__ == "__main__":
    unittest.main()
