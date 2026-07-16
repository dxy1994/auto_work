"""Worker 浏览器任务并发回归测试。"""

import asyncio
import pathlib
import sys
import threading
import time
import types
import unittest
from unittest import mock


WORKER_DIR = pathlib.Path(__file__).resolve().parents[1] / "worker"
sys.path.insert(0, str(WORKER_DIR))

from automation import chat_sender
from automation import audio_alert


class _FakePage:
    def __init__(self):
        self.closed = False

    async def goto(self, *args, **kwargs):
        return None

    async def wait_for_timeout(self, *args, **kwargs):
        return None

    async def wait_for_load_state(self, *args, **kwargs):
        return None

    async def wait_for_selector(self, *args, **kwargs):
        return None

    async def fill(self, *args, **kwargs):
        return None

    async def click(self, *args, **kwargs):
        return None

    async def close(self):
        self.closed = True


class _FakeSession:
    def __init__(self, owner_loop):
        self.owner_loop = owner_loop
        self._context = object()
        self.executed_loop = None
        self.transient_pages = set()
        self.page = _FakePage()
        self.allow_operation = True
        self.operation_count = 0

    def begin_transient_operation(self):
        if not self.allow_operation:
            return False
        self.operation_count += 1
        return True

    def end_transient_operation(self):
        self.operation_count -= 1

    async def new_page(self):
        self.executed_loop = asyncio.get_running_loop()
        return self.page

    def track_transient_page(self, page):
        self.transient_pages.add(id(page))

    def untrack_transient_page(self, page):
        self.transient_pages.discard(id(page))


class WorkerConcurrencyTest(unittest.TestCase):
    def test_greeting_runs_on_browser_session_owner_loop(self):
        owner_loop = asyncio.new_event_loop()
        loop_ready = threading.Event()

        def run_owner_loop():
            asyncio.set_event_loop(owner_loop)
            loop_ready.set()
            owner_loop.run_forever()

        owner_thread = threading.Thread(target=run_owner_loop, daemon=True)
        owner_thread.start()
        self.assertTrue(loop_ready.wait(1))

        session = _FakeSession(owner_loop)
        browser_session_module = types.ModuleType("automation.browser_session")

        class FakeBrowserSession:
            @classmethod
            def get_existing(cls, account_id):
                return session if account_id == 7 else None

        browser_session_module.BrowserSession = FakeBrowserSession
        previous_module = sys.modules.get("automation.browser_session")
        sys.modules["automation.browser_session"] = browser_session_module

        try:
            result = chat_sender.send_web_chat(
                7,
                "https://example.invalid/chat",
                [{"content": "hello"}],
            )
        finally:
            if previous_module is None:
                sys.modules.pop("automation.browser_session", None)
            else:
                sys.modules["automation.browser_session"] = previous_module
            owner_loop.call_soon_threadsafe(owner_loop.stop)
            owner_thread.join(timeout=1)
            owner_loop.close()

        self.assertTrue(result["success"], result)
        self.assertIs(session.executed_loop, owner_loop)
        self.assertTrue(session.page.closed)
        self.assertEqual(set(), session.transient_pages)
        self.assertEqual(0, session.operation_count)

    def test_greeting_rejects_closing_browser_session(self):
        session = _FakeSession(asyncio.new_event_loop())
        session.allow_operation = False
        try:
            result = asyncio.run(chat_sender._do_send_web_chat(
                session,
                "https://example.invalid/chat",
                [{"content": "hello"}],
            ))
        finally:
            session.owner_loop.close()

        self.assertFalse(result["success"])
        self.assertIn("正在关闭", result["message"])
        self.assertIsNone(session.executed_loop)

    def test_async_audio_does_not_block_event_loop(self):
        self.assertTrue(
            hasattr(audio_alert, "play_alert_audio_async"),
            "缺少异步语音播放入口",
        )

        def slow_audio(*args, **kwargs):
            time.sleep(0.2)
            return True

        async def scenario():
            with mock.patch.object(
                    audio_alert, "play_alert_audio", side_effect=slow_audio):
                task = asyncio.create_task(
                    audio_alert.play_alert_audio_async(text="测试"))
                started = time.monotonic()
                await asyncio.sleep(0.02)
                elapsed = time.monotonic() - started
                result = await task
                return elapsed, result

        elapsed, result = asyncio.run(scenario())
        self.assertLess(elapsed, 0.1)
        self.assertTrue(result)

    def test_async_audio_serializes_com_work_on_one_thread(self):
        worker_threads = set()

        def record_thread(*args, **kwargs):
            worker_threads.add(threading.get_ident())
            time.sleep(0.05)
            return True

        async def scenario():
            with mock.patch.object(
                    audio_alert, "play_alert_audio", side_effect=record_thread):
                return await asyncio.gather(
                    audio_alert.play_alert_audio_async(text="一"),
                    audio_alert.play_alert_audio_async(text="二"),
                )

        results = asyncio.run(scenario())
        self.assertEqual([True, True], results)
        self.assertEqual(1, len(worker_threads))

    def test_startup_cleanup_preserves_transient_chat_page(self):
        patchright_module = types.ModuleType("patchright")
        async_api_module = types.ModuleType("patchright.async_api")
        async_api_module.Page = object
        async_api_module.Browser = object
        async_api_module.BrowserContext = object
        async_api_module.async_playwright = lambda: None
        patchright_module.async_api = async_api_module
        sys.modules.setdefault("patchright", patchright_module)
        sys.modules.setdefault("patchright.async_api", async_api_module)

        from automation.order_monitor import BaseOrderMonitor

        class CleanupPage:
            def __init__(self, url):
                self.url = url
                self.closed = False

            async def close(self):
                self.closed = True

        worker_page = CleanupPage("https://example.invalid/orders")
        transient_page = CleanupPage("https://example.invalid/chat")
        stray_page = CleanupPage("about:blank")

        class Session:
            _context = types.SimpleNamespace(
                pages=[worker_page, transient_page, stray_page])

            @staticmethod
            def transient_page_ids():
                return {id(transient_page)}

        monitor = BaseOrderMonitor(
            task_id="test", website_id=1, account_id=7, start=time.time())
        monitor._session = Session()
        worker = types.SimpleNamespace(_page=worker_page)

        asyncio.run(monitor._close_non_worker_pages([worker]))

        self.assertFalse(worker_page.closed)
        self.assertFalse(transient_page.closed)
        self.assertTrue(stray_page.closed)


if __name__ == "__main__":
    unittest.main()
