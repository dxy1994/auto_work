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
    ManiaOrderWorker,
    ManiaRefreshWorker,
)
from monitor.monitoring.platforms import itemmania as itemmania_module  # noqa: E402


class _FakeSession:
    account_id = 4


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

    def test_refresh_worker_uses_locators_instead_of_element_handles(self):
        source = inspect.getsource(ManiaRefreshWorker._do_refresh)

        self.assertIn(".locator(", source)
        self.assertNotIn("query_selector", source)
        self.assertNotIn("networkidle", source)


if __name__ == "__main__":
    unittest.main()
