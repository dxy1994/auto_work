import ast
import unittest
from pathlib import Path


WORKER_ROOT = Path(__file__).resolve().parent.parent


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

    def test_cancelled_status_is_reported_before_browser_shutdown(self):
        source = (WORKER_ROOT / "monitor" / "monitoring" / "base.py").read_text(encoding="utf-8")
        report_index = source.index('self.task_id, "cancelled"')
        shutdown_index = source.index('shutdown(reason="user_cancel")')
        self.assertLess(report_index, shutdown_index)


if __name__ == "__main__":
    unittest.main()
