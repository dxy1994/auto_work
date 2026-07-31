import asyncio
import inspect
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch


WORKER_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKER_ROOT))

from monitor.monitoring.platforms import barotem as barotem_module  # noqa: E402
from monitor.monitoring.platforms.barotem import (  # noqa: E402
    BarotemMonitor,
    BarotemOrderWorker,
    BarotemRefreshWorker,
    ORDER_CONTENT_SELECTOR,
    ORDER_LIST_URL,
    SELL_LIST_URL,
    _parse_order_card_payload,
    _parse_refresh_product_id,
    _order_list_url,
    _product_list_url,
)
from monitor.orders.adapters import adapter_for  # noqa: E402


class _FakeSession:
    account_id = 7

    @staticmethod
    def is_login_page(_url):
        return False


class BarotemStructureTest(unittest.TestCase):
    def test_order_card_parser_matches_live_barotem_structure(self):
        parsed = _parse_order_card_payload({
            "order_no": "178522772911187596-36",
            "game_name": "아이온2",
            "server": "월드 거래소(마족) /",
            "title": "아이온2 키나 판매",
            "amount": "10",
            "price": "52,000 원",
            "buyer_onclick": (
                "dealinfo('102 107 102', '기어', "
                "'178522772911187596-36', '구매자 정보', 'itme');"
            ),
            "order_time": "26년 07월 28일 18:02:31",
            "mode": "4",
            "item_type": "money",
        })

        self.assertEqual("178522772911187596-36", parsed["order_no"])
        self.assertEqual("월드 거래소(마족)", parsed["server_code"])
        self.assertEqual("아이온2", parsed["game_name"])
        self.assertEqual("기어", parsed["buyer_character"])
        self.assertEqual("trading", parsed["status"])
        self.assertEqual("money", parsed["item_type"])

    def test_order_parser_rejects_missing_buyer_character(self):
        with self.assertRaisesRegex(ValueError, "买家角色名"):
            _parse_order_card_payload({
                "order_no": "178522772911187596-36",
                "game_name": "아이온2",
                "server": "월드 거래소(마족) /",
                "title": "아이온2 키나 판매",
                "amount": "10",
                "buyer_onclick": "",
                "mode": "4",
            })

    def test_completed_page_is_not_reportable_status(self):
        parsed = _parse_order_card_payload({
            "order_no": "178522772911187596-36",
            "game_name": "아이온2",
            "server": "월드 거래소(마족) /",
            "title": "아이온2 키나 판매",
            "amount": "10",
            "buyer_onclick": (
                "dealinfo('encoded', '기어', "
                "'178522772911187596-36', '구매자 정보', 'itme');"
            ),
            "mode": "5",
        })

        self.assertEqual("completed", parsed["status"])
        self.assertIsNone(adapter_for("barotem").normalize(parsed))

    def test_refresh_action_and_category_url_are_stable(self):
        self.assertEqual(
            "39182563",
            _parse_refresh_product_id("reregister('39182563')"),
        )
        url = _product_list_url("money")
        self.assertTrue(url.startswith(SELL_LIST_URL))
        self.assertIn("itemtype=money", url)
        self.assertIn("limit=500", url)
        order_url = _order_list_url("item")
        self.assertTrue(order_url.startswith(ORDER_LIST_URL))
        self.assertIn("itemtype=item", order_url)
        self.assertIn("limit=500", order_url)

    def test_monitor_uses_two_independent_workers(self):
        monitor = object.__new__(BarotemMonitor)
        monitor._session = _FakeSession()
        monitor.stop_event = None

        workers = monitor._get_workers()

        self.assertEqual(2, len(workers))
        self.assertIsInstance(workers[0], BarotemOrderWorker)
        self.assertIsInstance(workers[1], BarotemRefreshWorker)

    def test_order_extraction_does_not_fabricate_buyer_name(self):
        parser_source = inspect.getsource(_parse_order_card_payload)
        builder_source = inspect.getsource(
            BarotemMonitor._build_normalized_order)

        self.assertNotIn('f"buyer-', parser_source)
        self.assertIn("未提取到买家角色名", parser_source)
        self.assertIn("停止上报", builder_source)

    def test_refresh_flow_guards_against_double_submit(self):
        source = inspect.getsource(
            BarotemRefreshWorker._wait_refresh_result)

        self.assertIn("해당 물품에 끌어올리기를", source)
        self.assertIn("success_confirm_clicked", source)
        self.assertNotIn("reregistersave(", source)


class BarotemNavigationTest(unittest.IsolatedAsyncioTestCase):
    def _order_worker(self):
        monitor = SimpleNamespace(
            post_login_check=AsyncMock(return_value=False),
        )
        worker = BarotemOrderWorker(_FakeSession(), None, monitor)
        page = SimpleNamespace(
            url=ORDER_LIST_URL,
            reload=AsyncMock(),
            goto=AsyncMock(),
            wait_for_selector=AsyncMock(),
            evaluate=AsyncMock(return_value=100.0),
            is_closed=MagicMock(return_value=False),
        )
        worker._page = page
        return worker, page

    async def test_reload_timeout_accepts_new_ready_document(self):
        worker, page = self._order_worker()
        page.reload.side_effect = TimeoutError("commit timeout")
        page.evaluate.side_effect = [100.0, 200.0]

        await worker._reload_order_page(10000)

        page.goto.assert_not_awaited()
        page.wait_for_selector.assert_awaited_once_with(
            ORDER_CONTENT_SELECTOR,
            state="attached",
            timeout=20000,
        )
        self.assertEqual("commit", page.reload.await_args.kwargs["wait_until"])

    async def test_reload_without_document_change_has_one_controlled_goto(self):
        worker, page = self._order_worker()
        page.reload.side_effect = TimeoutError("commit timeout")
        page.evaluate.return_value = 100.0

        with patch.object(barotem_module, "COMMIT_GRACE_SECONDS", 0.0):
            await worker._reload_order_page(10000)

        page.goto.assert_awaited_once()
        self.assertEqual(ORDER_LIST_URL, page.goto.await_args.args[0])
        self.assertEqual("commit", page.goto.await_args.kwargs["wait_until"])

    async def test_business_popup_can_trigger_relogin(self):
        session = SimpleNamespace(
            account_id=7,
            is_login_page=MagicMock(return_value=False),
            relogin=AsyncMock(return_value={
                "status": "success",
                "message": "登录成功",
            }),
        )
        monitor = SimpleNamespace(
            post_login_check=AsyncMock(side_effect=[True, False]),
        )
        worker = BarotemOrderWorker(session, None, monitor)
        page = SimpleNamespace(
            url=ORDER_LIST_URL,
            goto=AsyncMock(),
            wait_for_selector=AsyncMock(),
            evaluate=AsyncMock(return_value=100.0),
            is_closed=MagicMock(return_value=False),
        )
        worker._page = page

        ready = await worker._ensure_order_page_ready(10000)

        self.assertTrue(ready)
        session.relogin.assert_awaited_once_with(page)
        page.goto.assert_awaited_once()
        self.assertEqual(ORDER_LIST_URL, page.goto.await_args.args[0])

    async def test_navigation_redirect_returns_control_to_relogin_flow(self):
        session = SimpleNamespace(
            account_id=7,
            is_login_page=MagicMock(return_value=True),
        )
        monitor = SimpleNamespace(
            post_login_check=AsyncMock(return_value=False),
        )
        worker = BarotemOrderWorker(session, None, monitor)
        page = SimpleNamespace(
            url="about:blank",
            goto=AsyncMock(),
            wait_for_selector=AsyncMock(),
            evaluate=AsyncMock(return_value=100.0),
            is_closed=MagicMock(return_value=False),
        )
        worker._page = page

        ready = await worker._goto_business_page(
            ORDER_LIST_URL,
            ORDER_CONTENT_SELECTOR,
            10000,
            reason="登录跳转测试",
        )

        self.assertFalse(ready)
        page.wait_for_selector.assert_not_awaited()

    async def test_refresh_categories_skip_zero_counts(self):
        monitor = SimpleNamespace(
            post_login_check=AsyncMock(return_value=False),
        )
        worker = BarotemRefreshWorker(_FakeSession(), None, monitor)
        locator = SimpleNamespace(
            evaluate_all=AsyncMock(return_value=[
                {"itemType": "id", "text": "계정\n0"},
                {"itemType": "money", "text": "게임머니\n5"},
                {"itemType": "item", "text": "아이템\n1"},
                {"itemType": "etc", "text": "기타\n0"},
                {"itemType": "gift", "text": "상품권\n0"},
            ]),
        )
        worker._page = SimpleNamespace(
            locator=MagicMock(return_value=locator),
        )

        result = await worker._available_product_types()

        self.assertEqual(["money", "item"], result)

    async def test_order_categories_skip_zero_counts(self):
        worker, _page = self._order_worker()
        locator = SimpleNamespace(
            evaluate_all=AsyncMock(return_value=[
                {"itemType": "id", "text": "계정\n0"},
                {"itemType": "money", "text": "게임머니\n2"},
                {"itemType": "item", "text": "아이템\n1"},
                {"itemType": "gift", "text": "상품권\n0"},
            ]),
        )
        worker._page.locator = MagicMock(return_value=locator)

        result = await worker._available_order_types()

        self.assertEqual(["money", "item"], result)

    async def test_order_worker_collects_each_nonempty_category(self):
        worker, page = self._order_worker()
        worker._available_order_types = AsyncMock(
            return_value=["money", "item"])
        worker._goto_business_page = AsyncMock()
        worker._recover_login_if_needed = AsyncMock(return_value=None)
        worker._monitor._collect_and_report_orders = AsyncMock(
            side_effect=[1, 2])

        async def update_url(url, *_args, **_kwargs):
            page.url = url
            return True

        worker._goto_business_page.side_effect = update_url

        reported = await worker._collect_all_order_categories(10000)

        self.assertEqual(3, reported)
        self.assertEqual(2, worker._goto_business_page.await_count)
        self.assertEqual(
            2, worker._monitor._collect_and_report_orders.await_count)


if __name__ == "__main__":
    unittest.main()
