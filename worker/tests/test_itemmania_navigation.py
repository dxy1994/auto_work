import asyncio
import inspect
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch


WORKER_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKER_ROOT))

from monitor.monitoring.platforms.itemmania import (  # noqa: E402
    COUPON_ADD_PATH,
    ManiaOrderWorker,
    ManiaRefreshWorker,
    SELL_ING_URL,
    SELL_REGIST_URL,
)
from monitor.monitoring.platforms import itemmania as itemmania_module  # noqa: E402
from monitor.browser.session import BrowserSession  # noqa: E402


class _FakeSession:
    account_id = 4

    @staticmethod
    def is_login_page(_url):
        return False


class ItemmaniaNavigationTest(unittest.IsolatedAsyncioTestCase):
    def _order_worker(self):
        monitor = SimpleNamespace(navigation_lock=asyncio.Lock())
        worker = ManiaOrderWorker(_FakeSession(), None, monitor)
        page = SimpleNamespace(
            url="https://www.itemmania.com/myroom/sell/sell_ing.html",
            reload=AsyncMock(),
            goto=AsyncMock(),
            wait_for_selector=AsyncMock(),
            evaluate=AsyncMock(return_value=100.0),
            is_closed=MagicMock(return_value=False),
        )
        worker._page = page
        return worker, page

    async def test_reload_timeout_uses_ready_page_without_second_goto(self):
        worker, page = self._order_worker()
        page.reload.side_effect = TimeoutError("commit timeout")
        page.evaluate.side_effect = [100.0, 200.0]

        await worker._reload_order_page(10000)

        page.goto.assert_not_awaited()
        page.wait_for_selector.assert_awaited_once()
        self.assertEqual("commit", page.reload.await_args.kwargs["wait_until"])

    async def test_reload_without_new_document_performs_only_one_goto(self):
        worker, page = self._order_worker()
        page.reload.side_effect = TimeoutError("commit timeout")
        page.evaluate.return_value = 100.0

        with patch.object(itemmania_module, "COMMIT_GRACE_SECONDS", 0.0):
            await worker._reload_order_page(10000)

        self.assertEqual(1, page.goto.await_count)
        self.assertEqual("commit", page.goto.await_args.kwargs["wait_until"])
        page.wait_for_selector.assert_awaited_once()

    async def test_initial_navigation_failure_is_not_immediately_repeated(self):
        worker, page = self._order_worker()
        page.url = "about:blank"
        page.goto.side_effect = TimeoutError("commit timeout")
        page.evaluate.return_value = 100.0

        with patch.object(itemmania_module, "COMMIT_GRACE_SECONDS", 0.0):
            with self.assertRaisesRegex(RuntimeError, "订单页初始化导航未提交"):
                await worker._ensure_order_page_ready(10000)

        self.assertEqual(1, page.goto.await_count)
        self.assertEqual("commit", page.goto.await_args.kwargs["wait_until"])

    async def test_order_worker_relogs_in_after_itemmania_redirect(self):
        session = SimpleNamespace(
            account_id=4,
            is_login_page=MagicMock(return_value=True),
            relogin=AsyncMock(return_value={
                "status": "success",
                "message": "登录成功",
            }),
        )
        monitor = SimpleNamespace(navigation_lock=asyncio.Lock())
        worker = ManiaOrderWorker(session, None, monitor)
        page = SimpleNamespace(
            url="https://www.itemmania.com/portal/user/p_login_form.html",
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
        self.assertEqual(SELL_ING_URL, page.goto.await_args.args[0])
        page.wait_for_selector.assert_awaited_once()

    async def test_order_worker_backs_off_after_relogin_failure(self):
        session = SimpleNamespace(
            account_id=4,
            is_login_page=MagicMock(return_value=True),
            relogin=AsyncMock(return_value={
                "status": "failed",
                "message": "密码错误",
            }),
        )
        monitor = SimpleNamespace(navigation_lock=asyncio.Lock())
        worker = ManiaOrderWorker(session, None, monitor)
        worker._page = SimpleNamespace(
            url="https://www.itemmania.com/portal/user/p_login_form.html",
        )

        first_ready = await worker._ensure_order_page_ready(10000)
        second_ready = await worker._ensure_order_page_ready(10000)

        self.assertFalse(first_ready)
        self.assertFalse(second_ready)
        self.assertEqual(1, worker._relogin_failures)
        self.assertGreater(worker._next_relogin_at, 0)
        session.relogin.assert_awaited_once_with(worker.page)

    async def test_order_worker_pauses_after_repeated_relogin_failures(self):
        session = SimpleNamespace(
            account_id=4,
            is_login_page=MagicMock(return_value=True),
            relogin=AsyncMock(return_value={
                "status": "failed",
                "message": "密码错误",
            }),
        )
        monitor = SimpleNamespace(navigation_lock=asyncio.Lock())
        worker = ManiaOrderWorker(session, None, monitor)
        worker._page = SimpleNamespace(
            url="https://www.itemmania.com/portal/user/p_login_form.html",
        )

        with patch.object(
                itemmania_module,
                "play_alert_audio_async",
                new=AsyncMock()) as alert:
            for _ in range(itemmania_module.RELOGIN_MAX_ATTEMPTS):
                worker._next_relogin_at = 0
                self.assertFalse(
                    await worker._ensure_order_page_ready(10000)
                )
            self.assertFalse(await worker._ensure_order_page_ready(10000))

        self.assertTrue(worker._relogin_disabled)
        self.assertEqual(
            itemmania_module.RELOGIN_MAX_ATTEMPTS,
            session.relogin.await_count,
        )
        alert.assert_awaited_once()

    async def test_refresh_commit_timeout_accepts_business_ready_page(self):
        monitor = SimpleNamespace(navigation_lock=asyncio.Lock())
        worker = ManiaRefreshWorker(_FakeSession(), None, monitor)
        page = SimpleNamespace(
            url="https://www.itemmania.com/myroom/sell/sell_regist.html",
            goto=AsyncMock(side_effect=TimeoutError("commit timeout")),
            wait_for_selector=AsyncMock(),
            evaluate=AsyncMock(side_effect=[100.0, 200.0]),
            is_closed=MagicMock(return_value=False),
        )
        worker._page = page

        await worker._goto_refresh_page(
            page.url, 10000, reason="测试导航")

        page.wait_for_selector.assert_awaited_once()
        self.assertEqual("commit", page.goto.await_args.kwargs["wait_until"])

    async def test_refresh_action_reloads_healthy_listing_document(self):
        monitor = SimpleNamespace(navigation_lock=asyncio.Lock())
        worker = ManiaRefreshWorker(_FakeSession(), None, monitor)
        worker._page = SimpleNamespace(
            url=SELL_REGIST_URL,
            reload=AsyncMock(),
            evaluate=AsyncMock(return_value=100.0),
            is_closed=MagicMock(return_value=False),
        )
        worker._wait_refresh_table = AsyncMock(return_value=True)
        worker._goto_refresh_page = AsyncMock()

        await worker._prepare_refresh_action_page(10000)

        worker.page.reload.assert_awaited_once_with(
            wait_until="commit",
            timeout=15000,
        )
        worker._wait_refresh_table.assert_awaited_once_with(10000)
        worker._goto_refresh_page.assert_not_awaited()

    async def test_refresh_action_recovers_when_listing_document_is_missing(self):
        monitor = SimpleNamespace(navigation_lock=asyncio.Lock())
        worker = ManiaRefreshWorker(_FakeSession(), None, monitor)
        worker._page = SimpleNamespace(url="about:blank")
        worker._wait_refresh_table = AsyncMock()
        worker._goto_refresh_page = AsyncMock()

        await worker._prepare_refresh_action_page(10000)

        worker._wait_refresh_table.assert_not_awaited()
        worker._goto_refresh_page.assert_awaited_once_with(
            SELL_REGIST_URL,
            10000,
            reason="刷新-恢复上架页",
        )

    async def test_refresh_reload_timeout_accepts_new_ready_document(self):
        monitor = SimpleNamespace(navigation_lock=asyncio.Lock())
        worker = ManiaRefreshWorker(_FakeSession(), None, monitor)
        worker._page = SimpleNamespace(
            url=SELL_REGIST_URL,
            reload=AsyncMock(side_effect=TimeoutError("commit timeout")),
            evaluate=AsyncMock(side_effect=[100.0, 200.0]),
            is_closed=MagicMock(return_value=False),
        )
        worker._wait_refresh_table = AsyncMock(return_value=True)
        worker._goto_refresh_page = AsyncMock()

        await worker._prepare_refresh_action_page(10000)

        worker._wait_refresh_table.assert_awaited_once_with(10000)
        worker._goto_refresh_page.assert_not_awaited()

    async def test_refresh_without_new_document_performs_controlled_goto(self):
        monitor = SimpleNamespace(navigation_lock=asyncio.Lock())
        worker = ManiaRefreshWorker(_FakeSession(), None, monitor)
        worker._page = SimpleNamespace(
            url=SELL_REGIST_URL,
            reload=AsyncMock(side_effect=TimeoutError("commit timeout")),
            evaluate=AsyncMock(return_value=100.0),
            is_closed=MagicMock(return_value=False),
        )
        worker._wait_refresh_table = AsyncMock()
        worker._goto_refresh_page = AsyncMock()

        with patch.object(itemmania_module, "COMMIT_GRACE_SECONDS", 0.0):
            await worker._prepare_refresh_action_page(10000)

        worker._wait_refresh_table.assert_not_awaited()
        worker._goto_refresh_page.assert_awaited_once_with(
            SELL_REGIST_URL,
            10000,
            reason="刷新-受控恢复上架页",
        )

    async def test_coupon_redirect_is_not_treated_as_refresh_success(self):
        monitor = SimpleNamespace(navigation_lock=asyncio.Lock())
        worker = ManiaRefreshWorker(_FakeSession(), None, monitor)
        page = SimpleNamespace(
            url=f"https://www.itemmania.com{COUPON_ADD_PATH}",
            is_closed=MagicMock(return_value=False),
        )
        worker._page = page
        worker._goto_refresh_page = AsyncMock()

        result = await worker._wait_refresh_result(100.0, 10000)

        self.assertEqual("coupon_required", result)
        worker._goto_refresh_page.assert_awaited_once_with(
            SELL_REGIST_URL,
            10000,
            reason="优惠券页-恢复上架页",
        )

    async def test_refresh_result_requires_a_new_business_document(self):
        monitor = SimpleNamespace(navigation_lock=asyncio.Lock())
        worker = ManiaRefreshWorker(_FakeSession(), None, monitor)
        page = SimpleNamespace(
            url=SELL_REGIST_URL,
            evaluate=AsyncMock(return_value=200.0),
            wait_for_selector=AsyncMock(),
            is_closed=MagicMock(return_value=False),
        )
        worker._page = page

        result = await worker._wait_refresh_result(100.0, 10000)

        self.assertEqual("refreshed", result)
        page.wait_for_selector.assert_awaited_once()

    def test_refresh_worker_has_no_coupon_cooldown(self):
        source = inspect.getsource(ManiaRefreshWorker.run)

        self.assertNotIn("coupon_blocked_until", source)
        self.assertNotIn("COUPON_RETRY_INTERVAL_SECONDS", source)
        self.assertIn("重新上架次数不足，请购买", source)
        self.assertIn("play_alert_audio_async", source)

    def test_refresh_worker_uses_locators_instead_of_element_handles(self):
        source = inspect.getsource(ManiaRefreshWorker._do_refresh)

        self.assertIn(".locator(", source)
        self.assertNotIn("query_selector", source)
        self.assertNotIn("networkidle", source)

    def test_only_refresh_worker_periodically_recycles_its_long_running_page(self):
        refresh_source = inspect.getsource(ManiaRefreshWorker.run)
        order_source = inspect.getsource(ManiaOrderWorker.run)

        self.assertIn("REFRESH_PAGE_MAX_ACTIONS", refresh_source)
        self.assertIn("recycle_page", refresh_source)
        self.assertNotIn("recycle_page", order_source)

    def test_worker_pages_navigate_independently_and_only_relogin_is_locked(self):
        navigation_source = "\n".join((
            inspect.getsource(ManiaOrderWorker._ensure_order_page_ready),
            inspect.getsource(ManiaOrderWorker._reload_order_page),
            inspect.getsource(ManiaRefreshWorker._do_refresh),
            inspect.getsource(ManiaRefreshWorker._ensure_refresh_page_ready),
        ))
        relogin_source = inspect.getsource(BrowserSession.relogin)

        self.assertNotIn("navigation_lock", navigation_source)
        self.assertFalse(hasattr(
            itemmania_module.ItemmaniaMonitor,
            "navigation_lock",
        ))
        self.assertIn("async with self._relogin_lock", relogin_source)

    async def test_refresh_worker_escalates_renderer_crash_for_page_rebuild(self):
        monitor = SimpleNamespace(
            navigation_lock=asyncio.Lock(),
            get_order_cfg=lambda: {"wait_timeout": 10000},
        )
        worker = ManiaRefreshWorker(_FakeSession(), None, monitor)
        worker._page = SimpleNamespace(
            is_closed=MagicMock(return_value=False),
        )
        worker._ensure_refresh_page_ready = AsyncMock()
        worker._sync_sales_products = AsyncMock()
        worker._do_refresh = AsyncMock(
            side_effect=RuntimeError("Page crashed: Out of Memory")
        )
        worker._last_refresh = (
            itemmania_module.datetime.datetime.now()
            - itemmania_module.datetime.timedelta(seconds=41)
        )

        with self.assertRaisesRegex(RuntimeError, "上架页已不可用"):
            await worker.run()

    def test_detail_extraction_does_not_fabricate_buyer_name(self):
        source = inspect.getsource(
            itemmania_module.ItemmaniaMonitor._fetch_order_detail)

        self.assertNotIn('f"buyer-', source)
        self.assertIn("구매자 캐릭터명", source)
        self.assertIn("停止上报", source)


if __name__ == "__main__":
    unittest.main()
