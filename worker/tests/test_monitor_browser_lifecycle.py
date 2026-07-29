import ast
import asyncio
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch


WORKER_ROOT = Path(__file__).resolve().parent.parent
import sys
sys.path.insert(0, str(WORKER_ROOT))

from monitor.browser.session import BrowserSession  # noqa: E402
from monitor.main import _heartbeat  # noqa: E402
from monitor.monitoring.worker import PageWorker  # noqa: E402


class _NoopPageWorker(PageWorker):
    async def run(self):
        return None


class MonitorBrowserLifecycleTest(unittest.TestCase):
    def test_heartbeat_reports_active_order_monitors_immediately(self):
        client = SimpleNamespace(
            local_ip="192.168.1.88",
            send=AsyncMock(side_effect=RuntimeError("stop after first heartbeat")),
        )
        task_manager = SimpleNamespace(snapshot=lambda: {
            4: {
                "task_id": "order-4",
                "kind": "order_check",
                "status": "running",
                "start_time": 1234.5,
            },
        })

        with self.assertRaisesRegex(RuntimeError, "stop after first heartbeat"):
            asyncio.run(_heartbeat(client, SimpleNamespace(task_manager=task_manager)))

        payload = client.send.await_args.args[0]
        self.assertEqual("monitor", payload["runtime"]["role"])
        self.assertEqual([{
            "account_id": 4,
            "task_id": "order-4",
            "status": "running",
            "start_time": 1234.5,
        }], payload["runtime"]["active_tasks"])

    def test_websocket_disconnect_does_not_cancel_monitor_tasks(self):
        source = (WORKER_ROOT / "monitor" / "main.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        connect_once = next(
            node for node in tree.body
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "_connect_once"
        )
        calls = [
            node for node in ast.walk(connect_once)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        ]
        self.assertFalse(any(call.func.attr == "cancel_all" for call in calls))

    def test_session_shutdown_is_only_requested_for_user_cancel(self):
        source = (WORKER_ROOT / "monitor" / "monitoring" / "base.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        shutdown_calls = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "shutdown"
        ]
        self.assertGreater(len(shutdown_calls), 0)
        for call in shutdown_calls:
            reason = next((kw.value for kw in call.keywords if kw.arg == "reason"), None)
            self.assertIsInstance(reason, ast.Constant)
            self.assertEqual("user_cancel", reason.value)

    def test_session_rejects_non_user_shutdown_reason(self):
        source = (WORKER_ROOT / "monitor" / "browser" / "session.py").read_text(encoding="utf-8")
        self.assertIn('if reason != "user_cancel":', source)
        self.assertIn("return False", source)

    def test_browser_crash_is_reset_and_restarted(self):
        session_source = (WORKER_ROOT / "monitor" / "browser" / "session.py").read_text(encoding="utf-8")
        monitor_source = (WORKER_ROOT / "monitor" / "monitoring" / "base.py").read_text(encoding="utf-8")
        self.assertIn("async def reset_after_crash", session_source)
        self.assertIn("not self._session.is_alive()", monitor_source)
        self.assertIn("await self._session.reset_after_crash()", monitor_source)

    def test_restored_tabs_are_kept_but_unusable_pages_are_replaced(self):
        session = BrowserSession(account_id=4)
        healthy_older = SimpleNamespace(
            url="https://example.com/orders",
            is_closed=MagicMock(return_value=False),
            evaluate=AsyncMock(return_value=1),
            close=AsyncMock(),
        )
        crashed = SimpleNamespace(
            url="https://example.com/crashed",
            is_closed=MagicMock(return_value=False),
            evaluate=AsyncMock(side_effect=RuntimeError("Page crashed")),
            close=AsyncMock(),
        )
        healthy_latest = SimpleNamespace(
            url="https://example.com/listing",
            is_closed=MagicMock(return_value=False),
            evaluate=AsyncMock(return_value=1),
            close=AsyncMock(),
        )
        blank = SimpleNamespace(
            url="about:blank",
            close=AsyncMock(),
        )
        session._context = SimpleNamespace(
            pages=[healthy_older, crashed, healthy_latest, blank],
            new_page=AsyncMock(),
        )

        main_page = asyncio.run(session._pick_main_page())

        self.assertIs(healthy_latest, main_page)
        crashed.close.assert_awaited_once()
        blank.close.assert_awaited_once()
        healthy_older.close.assert_not_awaited()

    def test_worker_runner_only_rebuilds_failed_pages(self):
        worker_source = (WORKER_ROOT / "monitor" / "monitoring" / "worker.py").read_text(encoding="utf-8")
        monitor_source = (WORKER_ROOT / "monitor" / "monitoring" / "base.py").read_text(encoding="utf-8")
        worker = _NoopPageWorker(SimpleNamespace(account_id=4), None)
        worker._page = SimpleNamespace(
            is_closed=MagicMock(return_value=False),
        )

        self.assertIn('page.on("crash"', worker_source)
        self.assertIn("if worker.page_failure_requires_rebuild(e):", monitor_source)
        self.assertIn("await worker.recover_page_after_failure(e)", monitor_source)
        self.assertFalse(worker.page_failure_requires_rebuild(
            RuntimeError("backend request failed")
        ))
        self.assertTrue(worker.page_failure_requires_rebuild(
            RuntimeError("Page crashed: renderer unavailable")
        ))

    def test_cancelled_status_is_reported_before_browser_shutdown(self):
        source = (WORKER_ROOT / "monitor" / "monitoring" / "base.py").read_text(encoding="utf-8")
        report_index = source.index('self.task_id, "cancelled"')
        shutdown_index = source.index('shutdown(reason="user_cancel")')
        self.assertLess(report_index, shutdown_index)

    def test_runtime_relogin_refreshes_cached_login_result(self):
        session = BrowserSession(
            account_id=4,
            login_url="https://www.itemmania.com/portal/user/p_login_form.html",
            username="user",
            password="password",
            login_config={"username_selector": "#id"},
        )
        session._login_done = True
        page = object()
        login_result = {"status": "success", "message": "登录成功"}

        with patch(
            "monitor.browser.login.do_login_async",
            new=AsyncMock(return_value=login_result),
        ) as do_login:
            result = asyncio.run(session.relogin(page))

        self.assertEqual(login_result, result)
        self.assertTrue(session._login_done)
        self.assertEqual(login_result, session._login_result)
        self.assertIs(page, do_login.await_args.kwargs["page"])

    def test_login_redirect_matches_configured_login_url(self):
        session = BrowserSession(
            account_id=4,
            login_url="https://www.itemmania.com/portal/user/p_login_form.html",
        )

        self.assertTrue(session.is_login_page(
            "https://www.itemmania.com/portal/user/p_login_form.html?return=myroom"
        ))
        self.assertFalse(session.is_login_page(
            "https://www.itemmania.com/myroom/sell/sell_ing.html"
        ))


if __name__ == "__main__":
    unittest.main()
