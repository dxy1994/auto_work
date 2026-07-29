import asyncio
import unittest
from unittest.mock import patch

from monitor.chat import sender
from monitor.monitoring.chat import normalize_chat_command, report_chat_result


class ChatCommandTest(unittest.TestCase):

    def test_normalize_legacy_greeting_as_chat(self):
        command = normalize_chat_command({
            "type": "greeting",
            "order_id": 42,
            "account_id": 5,
            "chat_url": "https://www.itemmania.com/chat?tid=42",
            "scripts": [{"content": "hello", "image_url": "/uploads/a.png"}],
        })

        self.assertEqual("greeting", command["purpose"])
        self.assertEqual("hello", command["messages"][0]["content"])
        self.assertEqual("#write_chat", command["target"]["input_selector"])

    def test_chat_result_keeps_automatic_and_manual_callbacks_separate(self):
        class FakeReporter:
            def __init__(self):
                self.calls = []

            def report_greeting_result(self, order_id, success, message):
                self.calls.append(("greeting", order_id, success, message))

            def report_chat_result(
                    self, request_id, order_id, success, message, purpose,
                    details):
                self.calls.append(
                    (
                        "chat",
                        request_id,
                        order_id,
                        success,
                        message,
                        purpose,
                        details,
                    ))

        reporter = FakeReporter()
        report_chat_result(
            reporter,
            {"purpose": "greeting", "order_id": 1, "request_id": "greeting-1"},
            {"success": True, "message": "ok"},
        )
        report_chat_result(
            reporter,
            {"purpose": "manual", "order_id": 2, "request_id": "chat-2"},
            {"success": False, "message": "failed"},
        )

        self.assertEqual([
            ("greeting", 1, True, "ok"),
            ("chat", "chat-2", 2, False, "failed", "manual", {}),
        ], reporter.calls)

    def test_sender_waits_for_each_message_in_order(self):
        events = []

        class FakeLocator:
            def __init__(self, selector):
                self.selector = selector

            @property
            def first(self):
                return self

            async def wait_for(self, **_kwargs):
                return None

            async def click(self, **_kwargs):
                events.append(f"click:{self.selector}")

        class FakeKeyboard:
            async def type(self, content, **_kwargs):
                events.append(f"type:{content}")

        class FakePage:
            def __init__(self):
                self.keyboard = FakeKeyboard()

            async def goto(self, url, **_kwargs):
                events.append(f"goto:{url}")

            async def wait_for_timeout(self, _milliseconds):
                return None

            def locator(self, selector):
                return FakeLocator(selector)

            async def close(self):
                events.append("close")

        class FakeSession:
            def __init__(self):
                self.page = FakePage()

            def begin_transient_operation(self):
                events.append("begin")
                return True

            async def new_page(self):
                return self.page

            def track_transient_page(self, _page):
                events.append("track")

            def untrack_transient_page(self, _page):
                events.append("untrack")

            def end_transient_operation(self):
                events.append("end")

        async def fake_send_image(_page, image_url, _target):
            events.append(f"image:{image_url}")

        with patch.object(sender, "_send_image_via_chat", fake_send_image):
            result = asyncio.run(sender._do_send_chat(
                FakeSession(),
                {
                    "url": "https://market.example.com/chat/42",
                    "input_selector": "#input",
                    "send_selector": "#send",
                    "file_selector": "#file",
                },
                [
                    {"content": "first", "image_urls": []},
                    {
                        "content": "second",
                        "image_urls": ["https://files.example.com/a.png"],
                    },
                ],
                keep_open=True,
            ))

        self.assertTrue(result["success"])
        relevant = [
            event for event in events
            if event.startswith(("type:", "image:", "click:#send"))
        ]
        self.assertEqual([
            "type:first",
            "click:#send",
            "image:https://files.example.com/a.png",
            "type:second",
            "click:#send",
        ], relevant)
        self.assertEqual(["close", "untrack", "end"], events[-3:])

    def test_sender_rejects_images_without_a_file_selector(self):
        result = asyncio.run(sender._do_send_chat(
            type("Session", (), {})(),
            {
                "url": "https://market.example.com/chat/42",
                "input_selector": "#input",
                "send_selector": "#send",
            },
            [{"image_urls": ["https://files.example.com/a.png"]}],
        ))

        self.assertEqual({
            "success": False,
            "message": "聊天图片上传控件选择器未配置",
        }, result)

    def test_delivery_confirmation_closes_chat_before_opening_order_detail(self):
        events = []

        class FakeLocator:
            def __init__(self, selector):
                self.selector = selector

            @property
            def first(self):
                return self

            async def wait_for(self, **_kwargs):
                return None

            async def click(self, **_kwargs):
                events.append(f"click:{self.selector}")

            async def inner_text(self):
                return "인계완료"

            async def count(self):
                return 1

            async def is_visible(self):
                return True

        class FakeKeyboard:
            async def type(self, content, **_kwargs):
                events.append(f"type:{content}")

        class FakePage:
            def __init__(self, name):
                self.name = name
                self.keyboard = FakeKeyboard()

            async def goto(self, url, **_kwargs):
                events.append(f"goto:{self.name}:{url}")

            async def wait_for_timeout(self, _milliseconds):
                return None

            def locator(self, selector):
                return FakeLocator(selector)

            def on(self, _event, _callback):
                return None

            async def close(self):
                events.append(f"close:{self.name}")

        class FakeSession:
            def __init__(self):
                self.pages = [FakePage("chat"), FakePage("detail")]

            def begin_transient_operation(self):
                return True

            async def new_page(self):
                return self.pages.pop(0)

            def track_transient_page(self, _page):
                return None

            def untrack_transient_page(self, _page):
                return None

            def end_transient_operation(self):
                return None

        async def fake_send_image(_page, image_url, _target):
            events.append(f"image:{image_url}")

        with patch.object(sender, "_send_image_via_chat", fake_send_image):
            result = asyncio.run(sender._do_send_chat_with_post_action(
                FakeSession(),
                {
                    "url": "https://www.itemmania.com/chat/42",
                    "input_selector": "#input",
                    "send_selector": "#send",
                    "file_selector": "#file",
                },
                [{
                    "image_urls": [
                        "/uploads/trade-screenshots/2026/07/29/proof.png",
                    ],
                }],
                {
                    "type": "confirm_delivery",
                    "detail_url": "https://www.itemmania.com/order/42",
                    "open_confirm_selector": "#trade_btn",
                    "confirm_selector": "#delivery-confirm",
                    "success_selector": ".active p",
                    "success_texts": ["인계완료", "판매완료"],
                },
                keep_open=True,
            ))

        self.assertTrue(result["success"])
        self.assertTrue(result["chat_sent"])
        self.assertTrue(result["chat_closed"])
        self.assertTrue(result["delivery_confirmed"])
        self.assertLess(
            events.index("close:chat"),
            events.index("goto:detail:https://www.itemmania.com/order/42"),
        )
        self.assertIn("click:#trade_btn", events)
        self.assertIn("click:#delivery-confirm", events)


if __name__ == "__main__":
    unittest.main()
