import ast
import asyncio
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch


WORKER_ROOT = Path(__file__).resolve().parent.parent
import sys
sys.path.insert(0, str(WORKER_ROOT))

from monitor.browser.session import BrowserSession  # noqa: E402


class MonitorBrowserLifecycleTest(unittest.TestCase):
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
        session_source = (WORKER_ROOT / "monitor" / "browser" / "session.py").read_text(encoding="utf-8")
        worker_source = (WORKER_ROOT / "monitor" / "monitoring" / "worker.py").read_text(encoding="utf-8")
        monitor_source = (WORKER_ROOT / "monitor" / "monitoring" / "base.py").read_text(encoding="utf-8")

        self.assertIn('"--restore-last-session"', session_source)
        self.assertIn("await self._page_is_usable(p)", session_source)
        self.assertIn("async def replace_claimed_page", session_source)
        self.assertIn('page.on("crash"', worker_source)
        self.assertIn("recover_page_after_failure", monitor_source)

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
