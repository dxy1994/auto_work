import asyncio
import unittest
from unittest.mock import patch

from monitor.chat import sender
from monitor.monitoring.chat import normalize_chat_command, report_chat_result


class ChatCommandTest(unittest.TestCase):

    def test_reply_wait_keeps_outer_chat_execution_alive(self):
        self.assertEqual(
            330,
            sender._chat_execution_timeout_seconds({
                "wait_for_reply": True,
                "reply_timeout_ms": 300_000,
            }),
        )
        self.assertEqual(
            120,
            sender._chat_execution_timeout_seconds({
                "wait_for_reply": False,
            }),
        )

    def test_configured_korean_affirmative_replies_are_accepted_exactly(self):
        allowed = sender.DEFAULT_KOREAN_AFFIRMATIVE_REPLIES

        accepted = (
            "네, 본인 맞습니다.",
            "네 본인 맛습니다.",
            "네 맞습니다",
            "예 맞습니다",
            "넵 맞습니다",
            "네",
            "넵",
            "맛습니다",
            "맞습니다",
            "맞아요",
            "본인입니다",
            "ok",
            "OK!",
            "네,저예요",
            "예",
            "네네",
            "  <네>!  ",
            "（ 네 ）",
        )
        for reply in accepted:
            with self.subTest(reply=reply):
                self.assertTrue(
                    sender._is_korean_affirmative_reply(reply, allowed)
                )

        self.assertFalse(sender._is_korean_affirmative_reply("네 감사합니다", allowed))
        self.assertFalse(sender._is_korean_affirmative_reply("아니요", allowed))
        self.assertFalse(sender._is_korean_affirmative_reply("네 아니요", allowed))
        self.assertFalse(sender._is_korean_affirmative_reply("네\n아니요", allowed))
        self.assertFalse(sender._is_korean_affirmative_reply("네 맞나요?", allowed))

    def test_reply_wait_uses_dynamic_question_as_conversation_anchor(self):
        class TextLocator:
            def __init__(self, item):
                self.item = item

            @property
            def first(self):
                return self

            async def count(self):
                return 1 if self.item["message"] else 0

            async def inner_text(self):
                return self.item["text"]

        class ItemLocator:
            def __init__(self, item):
                self.item = item

            def locator(self, _selector):
                return TextLocator(self.item)

            async def get_attribute(self, name):
                return self.item["class"] if name == "class" else None

        class ConversationLocator:
            def __init__(self, page):
                self.page = page

            async def count(self):
                return len(self.page.items)

            def nth(self, index):
                return ItemLocator(self.page.items[index])

        class Page:
            def __init__(self):
                self.items = [
                    {"class": "buyer", "text": "네", "message": True},
                    # 打开页面后、确认问句发出前到达的消息不能当作回答。
                    {"class": "buyer", "text": "아니요", "message": True},
                    {
                        "class": "self",
                        "text": "본인인가요? <네> 혹은 <아니요>라고 회답주세요",
                        "message": True,
                    },
                    # 问句后的己方截图应跳过。
                    {"class": "self", "text": "", "message": True},
                    {"class": "buyer", "text": "<네>", "message": True},
                    {"class": "buyer", "text": "아니요", "message": True},
                ]

            def locator(self, _selector):
                return ConversationLocator(self)

            async def wait_for_timeout(self, _milliseconds):
                return None

        reply, anchor_seen = asyncio.run(
            sender._wait_for_customer_reply_after_anchor(
                Page(),
                {
                    "conversation_selector": ".message",
                    "conversation_self_class": "self",
                    "conversation_text_selector": ".text",
                    "reply_timeout_ms": 1000,
                },
                start_index=1,
                anchor_text=(
                    "본인인가요? <네> 혹은 <아니요>라고 회답주세요"
                ),
            )
        )

        self.assertTrue(anchor_seen)
        self.assertEqual("<네>", reply)

    def test_itembay_reply_wait_refreshes_page_before_reading_new_reply(self):
        class TextLocator:
            def __init__(self, item):
                self.item = item

            @property
            def first(self):
                return self

            async def count(self):
                return 1

            async def inner_text(self):
                return self.item["text"]

        class ItemLocator:
            def __init__(self, item):
                self.item = item

            def locator(self, _selector):
                return TextLocator(self.item)

            async def get_attribute(self, name):
                return self.item["class"] if name == "class" else None

        class ConversationLocator:
            def __init__(self, page):
                self.page = page

            async def count(self):
                return len(self.page.items)

            def nth(self, index):
                return ItemLocator(self.page.items[index])

        class Page:
            def __init__(self):
                self.items = [
                    {"class": "send", "text": "네 또는 아니요라고 답해주세요"},
                ]
                self.reload_count = 0

            def locator(self, _selector):
                return ConversationLocator(self)

            async def reload(self, **_kwargs):
                self.reload_count += 1
                self.items.append(
                    {"class": "receive", "text": "네 맞습니다"}
                )

            async def wait_for_timeout(self, _milliseconds):
                await asyncio.sleep(0.002)

        page = Page()
        with patch.object(sender, "_dismiss_blocking_popup") as dismiss:
            dismiss.return_value = None
            reply, anchor_seen = asyncio.run(
                sender._wait_for_customer_reply_after_anchor(
                    page,
                    {
                        "conversation_selector": ".message",
                        "conversation_self_class": "send",
                        "conversation_text_selector": ".text",
                        "reply_timeout_ms": 1000,
                        "reply_refresh_interval_ms": 1,
                    },
                    start_index=0,
                    anchor_text="네 또는 아니요라고 답해주세요",
                )
            )

        self.assertTrue(anchor_seen)
        self.assertEqual("네 맞습니다", reply)
        self.assertEqual(1, page.reload_count)

    def test_reply_wait_does_not_use_buyer_message_when_anchor_missing(self):
        class TextLocator:
            def __init__(self, item):
                self.item = item

            @property
            def first(self):
                return self

            async def count(self):
                return 1

            async def inner_text(self):
                return self.item["text"]

        class ItemLocator:
            def __init__(self, item):
                self.item = item

            def locator(self, _selector):
                return TextLocator(self.item)

            async def get_attribute(self, name):
                return self.item["class"] if name == "class" else None

        class ConversationLocator:
            def __init__(self, page):
                self.page = page

            async def count(self):
                return len(self.page.items)

            def nth(self, index):
                return ItemLocator(self.page.items[index])

        class Page:
            def __init__(self):
                self.items = [
                    {"class": "me", "text": "질문입니다"},
                    {"class": "another", "text": "네"},
                ]

            def locator(self, _selector):
                return ConversationLocator(self)

            async def wait_for_timeout(self, _milliseconds):
                await asyncio.sleep(0.002)

        page = Page()
        reply, anchor_seen = asyncio.run(
            sender._wait_for_customer_reply_after_anchor(
                page,
                {
                    "conversation_selector": ".message",
                    "conversation_self_class": "me",
                    "conversation_text_selector": ".text",
                    "reply_timeout_ms": 500,
                },
                start_index=0,
                anchor_text="다음은 아님",
            )
        )

        self.assertFalse(anchor_seen)
        self.assertIsNone(reply)

    def test_reply_wait_rescans_when_image_inserts_anchor_before_cursor(self):
        class TextLocator:
            def __init__(self, item):
                self.item = item

            @property
            def first(self):
                return self

            async def count(self):
                return 1

            async def inner_text(self):
                return self.item["text"]

        class ItemLocator:
            def __init__(self, item):
                self.item = item

            def locator(self, _selector):
                return TextLocator(self.item)

            async def get_attribute(self, name):
                return self.item["class"] if name == "class" else None

        class ConversationLocator:
            def __init__(self, page):
                self.page = page

            async def count(self):
                return len(self.page.items)

            def nth(self, index):
                return ItemLocator(self.page.items[index])

        class Page:
            def __init__(self):
                self.items = [
                    {"class": "another", "text": "아닙니다."},
                    {"class": "me", "text": ""},
                ]
                self.inserted = False

            def locator(self, _selector):
                return ConversationLocator(self)

            async def wait_for_timeout(self, _milliseconds):
                if not self.inserted:
                    self.inserted = True
                    self.items.insert(1, {
                        "class": "me",
                        "text": "지금 거래하시는 분이 본인이라면 네라고 답장해주세요",
                    })
                    self.items.append({"class": "another", "text": "네"})
                await asyncio.sleep(0.002)

        reply, anchor_seen = asyncio.run(
            sender._wait_for_customer_reply_after_anchor(
                Page(),
                {
                    "conversation_selector": ".chat_item",
                    "conversation_self_class": "me",
                    "conversation_text_selector": ".chat_msg",
                    "reply_timeout_ms": 1000,
                },
                start_index=1,
                anchor_text=(
                    "지금 거래하시는 분이 본인이라면 네라고 답장해주세요"
                ),
            )
        )

        self.assertTrue(anchor_seen)
        self.assertEqual("네", reply)

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

    def test_normalize_delivery_action_without_duplicate_chat_message(self):
        command = normalize_chat_command({
            "type": "chat_command",
            "request_id": "delivery-1",
            "purpose": "delivery_confirmation",
            "messages": [],
            "target": {"url": "https://www.barotem.com/mypage/sellview/4"},
            "post_action": {
                "type": "confirm_delivery",
                "skip_chat": True,
            },
        })

        self.assertEqual([], command["messages"])
        self.assertTrue(command["post_action"]["skip_chat"])

    def test_delivery_action_only_does_not_open_chat_or_send_image(self):
        calls = []

        async def confirm_delivery(_session, action):
            calls.append(action)
            return {"success": True, "message": "confirmed"}

        with patch.object(sender, "_do_confirm_delivery", confirm_delivery):
            result = asyncio.run(sender._do_send_chat_with_post_action(
                object(),
                {},
                [],
                {
                    "type": "confirm_delivery",
                    "skip_chat": True,
                },
            ))

        self.assertTrue(result["success"])
        self.assertFalse(result["chat_sent"])
        self.assertTrue(result["proof_already_sent"])
        self.assertTrue(result["delivery_confirmed"])
        self.assertEqual(1, len(calls))

    def test_completion_chat_keeps_previous_proof_marker(self):
        async def send_chat(_session, _target, _messages, keep_open=False):
            return {"success": True, "message": "sent"}

        async def confirm_delivery(_session, _action):
            return {"success": True, "message": "confirmed"}

        with (
            patch.object(sender, "_do_send_chat", send_chat),
            patch.object(sender, "_do_confirm_delivery", confirm_delivery),
        ):
            result = asyncio.run(sender._do_send_chat_with_post_action(
                object(),
                {},
                [{"content": "交易完成，谢谢"}],
                {
                    "type": "confirm_delivery",
                    "skip_chat": False,
                    "proof_already_sent": True,
                },
            ))

        self.assertTrue(result["success"])
        self.assertTrue(result["chat_sent"])
        self.assertTrue(result["chat_closed"])
        self.assertTrue(result["proof_already_sent"])
        self.assertTrue(result["delivery_confirmed"])

    def test_completion_chat_failure_does_not_block_delivery(self):
        async def send_chat(_session, _target, _messages, keep_open=False):
            return {"success": False, "message": "聊天发送失败"}

        async def confirm_delivery(_session, _action):
            return {"success": True, "message": "confirmed"}

        with (
            patch.object(sender, "_do_send_chat", send_chat),
            patch.object(sender, "_do_confirm_delivery", confirm_delivery),
        ):
            result = asyncio.run(sender._do_send_chat_with_post_action(
                object(),
                {},
                [{"content": "交易完成，谢谢"}],
                {
                    "type": "confirm_delivery",
                    "skip_chat": False,
                    "proof_already_sent": True,
                    "chat_failure_non_blocking": True,
                },
            ))

        self.assertTrue(result["success"])
        self.assertFalse(result["chat_sent"])
        self.assertTrue(result["proof_already_sent"])
        self.assertEqual("聊天发送失败", result["completion_message_error"])
        self.assertTrue(result["delivery_confirmed"])

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

            async def wait_for_timeout(self, milliseconds):
                events.append(f"wait:{milliseconds}")

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
        self.assertLess(events.index("wait:10000"), events.index("close"))
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

    def test_itembay_sender_verifies_message_appears_in_chat(self):
        events = []

        class FakeLocator:
            def __init__(self, page, selector):
                self.page = page
                self.selector = selector

            @property
            def first(self):
                return self

            async def wait_for(self, **_kwargs):
                state = _kwargs.get("state")
                if self.selector == "#sTalkPop" and state == "hidden":
                    if self.page.popup_visible:
                        raise AssertionError("遮挡弹窗仍然可见")
                    return None
                if self.selector in {"#txtAreaMsgSend", "#btnSend"}:
                    if self.page.popup_visible:
                        raise AssertionError("遮挡弹窗关闭前不能操作聊天控件")
                return None

            async def is_enabled(self):
                return True

            async def count(self):
                if self.selector == "#chat_container .list_message li.send":
                    return self.page.sent_count
                return 1

            async def click(self, **_kwargs):
                events.append(f"click:{self.selector}")
                if self.selector == "#sTalkPop .btn_pop_close":
                    self.page.popup_visible = False
                if self.selector == "#btnSend":
                    self.page.sent_count += 1

        class FakeKeyboard:
            async def type(self, content, **_kwargs):
                events.append(f"type:{content}")

        class FakePage:
            def __init__(self):
                self.keyboard = FakeKeyboard()
                self.sent_count = 0
                self.popup_visible = True

            async def goto(self, url, **_kwargs):
                events.append(f"goto:{url}")

            async def wait_for_timeout(self, milliseconds):
                events.append(f"wait:{milliseconds}")

            def locator(self, selector):
                return FakeLocator(self, selector)

            async def close(self):
                events.append("close")

        class FakeSession:
            def __init__(self):
                self.page = FakePage()

            def begin_transient_operation(self):
                return True

            async def new_page(self):
                return self.page

            def track_transient_page(self, _page):
                return None

            def untrack_transient_page(self, _page):
                return None

            def end_transient_operation(self):
                return None

        session = FakeSession()
        result = asyncio.run(sender._do_send_chat(
            session,
            {
                "url": (
                    "https://www.itembay.com/ibmessenger/"
                    "bayTalkChatTran?iTranSeq=96370042"
                ),
                "input_selector": "#txtAreaMsgSend",
                "send_selector": "#btnSend",
                "file_selector": "#txtScreenShot",
                "blocking_popup_selector": "#sTalkPop",
                "blocking_popup_close_selector": (
                    "#sTalkPop .btn_pop_close"
                ),
                "blocking_popup_wait_ms": 1000,
                "sent_selector": "#chat_container .list_message li.send",
                "sent_timeout_ms": 1000,
                "max_text_length": 800,
                "max_image_bytes": 5 * 1024 * 1024,
            },
            [{"content": "안녕하세요", "image_urls": []}],
        ))

        self.assertTrue(result["success"])
        self.assertFalse(session.page.popup_visible)
        self.assertLess(
            events.index("click:#sTalkPop .btn_pop_close"),
            events.index("click:#txtAreaMsgSend"),
        )
        self.assertIn("type:안녕하세요", events)
        self.assertIn("click:#btnSend", events)
        self.assertEqual(1, session.page.sent_count)

    def test_itembay_sender_rejects_text_over_live_limit(self):
        with self.assertRaisesRegex(ValueError, "800"):
            sender._normalize_target(
                {
                    "url": (
                        "https://www.itembay.com/ibmessenger/"
                        "bayTalkChatTran?iTranSeq=96370042"
                    ),
                    "input_selector": "#txtAreaMsgSend",
                    "send_selector": "#btnSend",
                    "max_text_length": 800,
                },
                [{"content": "x" * 801, "image_urls": []}],
            )

    def test_itembay_target_gets_live_blocking_popup_defaults(self):
        target = sender._normalize_target(
            {
                "url": (
                    "https://www.itembay.com/ibmessenger/"
                    "bayTalkChatTran?iTranSeq=96370042"
                ),
                "input_selector": "#txtAreaMsgSend",
                "send_selector": "#btnSend",
            },
            [{"content": "hello", "image_urls": []}],
        )

        self.assertEqual("#sTalkPop", target["blocking_popup_selector"])
        self.assertEqual(
            "#sTalkPop .btn_pop_close",
            target["blocking_popup_close_selector"],
        )

    def test_itembay_missing_blocking_popup_is_a_normal_path(self):
        class MissingPopupLocator:
            @property
            def first(self):
                return self

            async def wait_for(self, **_kwargs):
                raise TimeoutError("popup not shown")

            async def click(self, **_kwargs):
                raise AssertionError("隐藏弹窗不应执行点击")

        class PopupFreePage:
            def locator(self, _selector):
                return MissingPopupLocator()

        dismissed = asyncio.run(sender._dismiss_blocking_popup(
            PopupFreePage(),
            {
                "blocking_popup_selector": "#sTalkPop",
                "blocking_popup_close_selector": (
                    "#sTalkPop .btn_pop_close"
                ),
                "blocking_popup_wait_ms": 100,
            },
        ))

        self.assertFalse(dismissed)

    def test_barotem_resolver_uses_completed_list_as_fallback(self):
        events = []

        class FakeValueLocator:
            def __init__(self, value=None, count=1):
                self.value = value
                self._count = count

            @property
            def first(self):
                return self

            async def count(self):
                return self._count

            async def get_attribute(self, _name):
                return self.value

            async def wait_for(self, **_kwargs):
                return None

        class FakeCard:
            def locator(self, selector):
                if selector == "input.product_checkbox":
                    return FakeValueLocator("178583752411285073-61")
                if selector == '[onclick*="/chat/view?jangNum="]':
                    return FakeValueLocator(
                        "ycommon.openChat('/chat/view?jangNum=9161506>', "
                        "'happy_chating_mypage','1000','1000');"
                    )
                return FakeValueLocator(count=0)

        class FakeCards:
            def __init__(self, available):
                self.available = available

            async def count(self):
                return 1 if self.available else 0

            def nth(self, _index):
                return FakeCard()

        class FakePage:
            def __init__(self):
                self.completed = False

            async def goto(self, url, **_kwargs):
                events.append(url)
                self.completed = "/sellview/5" in url

            def locator(self, selector):
                if selector == ".product_contents":
                    return FakeValueLocator()
                if selector == ".product_contents .product_wrap":
                    return FakeCards(self.completed)
                raise AssertionError(selector)

        list_url = (
            "https://www.barotem.com/mypage/sellview/4?mode=4&"
            "itemtype=money&source_order_no=178583752411285073-61"
        )
        chat_url = asyncio.run(sender._resolve_barotem_conversation(
            FakePage(),
            {
                "url": list_url,
                "order_no": "178583752411285073-61",
            },
        ))

        self.assertEqual(
            "https://www.barotem.com/chat/view?jangNum=9161506",
            chat_url,
        )
        self.assertIn("/mypage/sellview/4", events[0])
        self.assertIn("/mypage/sellview/5", events[1])
        self.assertEqual(chat_url, events[2])

    def test_barotem_resolver_opens_cached_chat_without_order_list(self):
        chat_url = "https://www.barotem.com/chat/view?jangNum=9161506"
        events = []

        class FakeSession:
            def cached_conversation_url(self, platform, order_no):
                events.append(f"cache:{platform}:{order_no}")
                return chat_url

            def forget_conversation_url(self, *_args):
                raise AssertionError("有效缓存不应被清理")

        class FakePage:
            async def goto(self, url, **_kwargs):
                events.append(f"goto:{url}")

            def locator(self, _selector):
                raise AssertionError("命中缓存后不应扫描订单列表")

        resolved = asyncio.run(sender._resolve_barotem_conversation(
            FakePage(),
            {
                "url": "https://www.barotem.com/mypage/sellview/4",
                "order_no": "178583752411285073-61",
            },
            session=FakeSession(),
        ))

        self.assertEqual(chat_url, resolved)
        self.assertEqual([
            "cache:barotem:178583752411285073-61",
            f"goto:{chat_url}",
        ], events)

    def test_barotem_target_requires_a_real_order_number(self):
        with self.assertRaisesRegex(ValueError, "Barotem order number"):
            sender._normalize_target(
                {
                    "url": "https://www.barotem.com/mypage/sellview/4",
                    "input_selector": "#message",
                    "send_selector": ".chat_send_btn",
                    "conversation_resolver": "barotem_order_list",
                    "order_no": "not-an-order",
                },
                [{"content": "hello", "image_urls": []}],
            )

    def test_barotem_image_submit_needs_no_attachment_config(self):
        target = sender._normalize_target(
            {
                "url": "https://www.barotem.com/mypage/sellview/4",
                "input_selector": "#message",
                "send_selector": ".chat_send_btn",
                "conversation_resolver": "barotem_order_list",
                "order_no": "178583752411285073-61",
                "barotem_image_submit": True,
            },
            [{"content": "", "image_urls": ["https://example.com/a.png"]}],
        )

        self.assertTrue(target["barotem_image_submit"])
        self.assertEqual("", target["file_selector"])
        self.assertEqual("", target["upload_send_selector"])

    def test_itembay_image_selection_auto_sends_and_verifies_receipt(self):
        class FakeResponse:
            headers = {"Content-Type": "image/png"}

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

            def raise_for_status(self):
                return None

            def iter_content(self, _chunk_size):
                return iter((b"png-image",))

        class FakeLocator:
            def __init__(self, page, selector):
                self.page = page
                self.selector = selector

            @property
            def first(self):
                return self

            async def count(self):
                if self.selector == "#chat_container .list_message li.send":
                    return self.page.sent_count
                return 1

            async def set_input_files(self, _path):
                self.page.sent_count += 1

        class FakePage:
            def __init__(self):
                self.sent_count = 0

            def locator(self, selector):
                return FakeLocator(self, selector)

            async def wait_for_timeout(self, _milliseconds):
                return None

        page = FakePage()
        with patch("requests.get", return_value=FakeResponse()):
            asyncio.run(sender._send_image_via_chat(
                page,
                "https://files.example.com/proof.png",
                {
                    "file_selector": "#txtScreenShot",
                    "upload_auto_send": True,
                    "sent_selector": (
                        "#chat_container .list_message li.send"
                    ),
                    "sent_timeout_ms": 1000,
                    "max_image_bytes": 5 * 1024 * 1024,
                },
            ))

        self.assertEqual(1, page.sent_count)

    def test_itemmania_image_upload_waits_for_successful_server_receipt(self):
        class Response:
            url = "https://www.itemmania.com/myroom/chat/ajax_send_file.php"
            ok = True
            status = 200

            async def json(self):
                return {"RST": True, "DATA2": ["proof.png"]}

        class ResponseInfo:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return None

            @property
            def value(self):
                async def result():
                    return Response()
                return result()

        class Page:
            def __init__(self):
                self.timeout = None

            def expect_response(self, predicate, timeout):
                self.timeout = timeout
                self.asserted = predicate(Response())
                return ResponseInfo()

        class FileInput:
            def __init__(self):
                self.path = None

            async def set_input_files(self, path):
                self.path = path

        page = Page()
        file_input = FileInput()
        asyncio.run(sender._select_itemmania_image_and_verify_upload(
            page,
            file_input,
            "proof.png",
            {"image_upload_timeout_ms": 30_000},
        ))

        self.assertTrue(page.asserted)
        self.assertEqual(30_000, page.timeout)
        self.assertEqual("proof.png", file_input.path)

    def test_itemmania_image_upload_surfaces_platform_error(self):
        class Response:
            url = "https://www.itemmania.com/myroom/chat/ajax_send_file.php"
            ok = True
            status = 200

            async def json(self):
                return {"RST": False, "MSG": "이미지 업로드 실패"}

        class ResponseInfo:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return None

            @property
            def value(self):
                async def result():
                    return Response()
                return result()

        class Page:
            def expect_response(self, _predicate, _timeout=None, **_kwargs):
                return ResponseInfo()

        class FileInput:
            async def set_input_files(self, _path):
                return None

        with self.assertRaisesRegex(
                RuntimeError, "ItemMania 图片上传失败"):
            asyncio.run(sender._select_itemmania_image_and_verify_upload(
                Page(),
                FileInput(),
                "proof.png",
                {},
            ))

    def test_itembay_sent_receipt_refreshes_non_realtime_chat(self):
        class SentLocator:
            def __init__(self, page):
                self.page = page

            async def count(self):
                return self.page.sent_count

        class Page:
            def __init__(self):
                self.sent_count = 0
                self.reload_count = 0

            def locator(self, _selector):
                return SentLocator(self)

            async def reload(self, **_kwargs):
                self.reload_count += 1
                self.sent_count = 1

            async def wait_for_timeout(self, _milliseconds):
                await asyncio.sleep(0.002)

        page = Page()
        with patch.object(sender, "_dismiss_blocking_popup") as dismiss:
            dismiss.return_value = None
            sent = asyncio.run(sender._wait_for_sent_message(
                page,
                {
                    "sent_selector": ".send",
                    "sent_timeout_ms": 1000,
                    "reply_refresh_interval_ms": 1,
                },
                previous_count=0,
            ))

        self.assertTrue(sent)
        self.assertEqual(1, page.reload_count)

    def test_itemmania_image_receipt_refreshes_history_after_timeout(self):
        class SentLocator:
            def __init__(self, page):
                self.page = page

            async def count(self):
                return self.page.sent_count

        class Page:
            def __init__(self):
                self.sent_count = 0
                self.reload_count = 0

            def locator(self, _selector):
                return SentLocator(self)

            async def reload(self, **_kwargs):
                self.reload_count += 1
                self.sent_count = 1

            async def wait_for_timeout(self, _milliseconds):
                await asyncio.sleep(0.03)

        page = Page()
        with patch.object(sender, "_dismiss_blocking_popup") as dismiss:
            dismiss.return_value = None
            sent = asyncio.run(sender._wait_for_sent_message(
                page,
                {
                    "sent_selector": ".chat_item.me",
                    "sent_timeout_ms": 100,
                    "sent_refresh_on_timeout": True,
                    "sent_refresh_timeout_ms": 100,
                },
                previous_count=0,
            ))

        self.assertTrue(sent)
        self.assertEqual(1, page.reload_count)

    def test_barotem_dispatches_paste_event_then_clicks_real_send(self):
        events = []

        class FakeResponse:
            headers = {"Content-Type": "image/png"}

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

            def raise_for_status(self):
                return None

            def iter_content(self, _chunk_size):
                return iter((b"png-image",))

        class FakeLocator:
            def __init__(self, page, selector):
                self.page = page
                self.selector = selector

            @property
            def first(self):
                return self

            async def count(self):
                if self.selector == "#chatBox .from_me":
                    return self.page.sent_count
                if self.selector == "#imgpopup.inline .imgview li":
                    return 1 if self.page.preview_ready else 0
                return 1

            async def wait_for(self, **_kwargs):
                events.append("barotem:form-ready")

            async def set_input_files(self, _path):
                events.append("barotem:file-selected")

            async def click(self, **_kwargs):
                if self.selector == "#imgpopup.inline .chat_send_btn":
                    events.append("barotem:confirm-clicked")
                    self.page.sent_count += 1

        class FakePage:
            def __init__(self):
                self.sent_count = 0
                self.preview_ready = False

            def locator(self, selector):
                return FakeLocator(self, selector)

            async def evaluate(self, script, _arg=None):
                if "input.type = 'file'" in script:
                    self.assert_no_visual_trigger = (
                        "createElement('button')" not in script
                        and "onclick" not in script
                    )
                    events.append("barotem:input-created")
                    return None
                if "new ClipboardEvent('paste'" in script:
                    self.assert_paste_event = (
                        "new DataTransfer()" in script
                        and "transfer.items.add(file)" in script
                        and "clipboardData: transfer" in script
                        and "document.dispatchEvent(pasteEvent)" in script
                        and "window.imgchg" not in script
                        and "window.confirmAndSend" not in script
                    )
                    events.append("barotem:paste-dispatched")
                    self.preview_ready = True
                    return {"success": True, "error": ""}
                events.append("barotem:input-removed")
                return None

            async def wait_for_timeout(self, _milliseconds):
                return None

        page = FakePage()
        with patch("requests.get", return_value=FakeResponse()):
            asyncio.run(sender._send_image_via_chat(
                page,
                "https://files.example.com/proof.png",
                {
                    "barotem_image_submit": True,
                    "sent_selector": "#chatBox .from_me",
                    "sent_timeout_ms": 1000,
                },
            ))

        self.assertEqual(1, page.sent_count)
        self.assertIn("barotem:form-ready", events)
        self.assertIn("barotem:input-created", events)
        self.assertIn("barotem:file-selected", events)
        self.assertIn("barotem:paste-dispatched", events)
        self.assertIn("barotem:confirm-clicked", events)
        self.assertTrue(page.assert_no_visual_trigger)
        self.assertTrue(page.assert_paste_event)

    def test_delivery_confirmation_closes_chat_before_opening_order_detail(self):
        events = []

        class FakeLocator:
            def __init__(self, selector, page):
                self.selector = selector
                self.page = page

            @property
            def first(self):
                return self

            async def wait_for(self, **_kwargs):
                return None

            async def click(self, **_kwargs):
                events.append(f"click:{self.selector}")
                if self.selector == "#delivery-confirm":
                    self.page.status_text = "인계완료"

            async def inner_text(self):
                return self.page.status_text

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
                self.status_text = "판매중" if name == "detail" else ""

            async def goto(self, url, **_kwargs):
                events.append(f"goto:{self.name}:{url}")

            async def wait_for_timeout(self, milliseconds):
                events.append(f"wait:{self.name}:{milliseconds}")

            def locator(self, selector):
                return FakeLocator(selector, self)

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
            events.index("wait:chat:10000"),
            events.index("close:chat"),
        )
        self.assertLess(
            events.index("close:chat"),
            events.index("goto:detail:https://www.itemmania.com/order/42"),
        )
        self.assertIn("click:#trade_btn", events)
        self.assertIn("click:#delivery-confirm", events)

    def test_barotem_delivery_confirmation_reopens_chat_and_requests_receipt(self):
        events = []

        class StageLocator:
            def __init__(self, page, index=None):
                self.page = page
                self.index = index

            @property
            def first(self):
                return StageLocator(self.page, 0)

            async def wait_for(self, **_kwargs):
                return None

            async def count(self):
                return 3

            def nth(self, index):
                return StageLocator(self.page, index)

            async def get_attribute(self, name):
                if name == "class":
                    return "on" if self.index == 1 else ""
                return None

            async def inner_text(self):
                return ("거래 대기", "결제 완료", "거래 완료")[self.index]

        class ActionLocator:
            def __init__(self, selector, page):
                self.selector = selector
                self.page = page

            @property
            def first(self):
                return self

            async def wait_for(self, **_kwargs):
                return None

            async def click(self, **_kwargs):
                events.append(f"click:{self.selector}")
                if self.selector == "#commonAlert .common_alert_check":
                    self.page.status_text = (
                        "구매자에게 인수확인 요청하였습니다."
                    )

            async def count(self):
                return 1

            async def is_visible(self):
                return True

            async def inner_text(self):
                return self.page.status_text

        class FakePage:
            def __init__(self):
                self.status_text = ""

            async def wait_for_timeout(self, milliseconds):
                events.append(f"wait:{milliseconds}")

            def locator(self, selector):
                if selector == ".chat_info_process > div":
                    return StageLocator(self)
                return ActionLocator(selector, self)

            def on(self, _event, _callback):
                return None

            async def close(self):
                events.append("close")

        class FakeSession:
            def __init__(self):
                self.page = FakePage()

            def begin_transient_operation(self):
                return True

            async def new_page(self):
                return self.page

            def track_transient_page(self, _page):
                return None

            def untrack_transient_page(self, _page):
                return None

            def end_transient_operation(self):
                return None

        async def resolve_chat(page, target, session=None):
            self.assertIsNotNone(session)
            self.assertEqual(
                "178602140511313632-34",
                target["order_no"],
            )
            events.append("resolve-chat")
            return "https://www.barotem.com/chat/view?jangNum=9187651"

        with patch.object(
                sender, "_resolve_barotem_conversation", resolve_chat):
            result = asyncio.run(sender._do_confirm_delivery(
                FakeSession(),
                {
                    "type": "confirm_delivery",
                    "detail_url": (
                        "https://www.barotem.com/mypage/sellview/4"
                        "?mode=4&itemtype=money&page=1&limit=500"
                    ),
                    "conversation_resolver": "barotem_order_list",
                    "order_no": "178602140511313632-34",
                    "ready_selector": ".chat_info_process",
                    "open_confirm_selector": "#state5",
                    "confirm_selector": (
                        "#commonAlert .common_alert_check"
                    ),
                    "success_selector": (
                        "#commonAlert .common_alert_wrap h2"
                    ),
                    "success_texts": [
                        "구매자에게 인수확인 요청하였습니다.",
                    ],
                    "success_before_reload": True,
                    "stage_selector": ".chat_info_process > div",
                    "stage_active_class": "on",
                    "pending_stage": 2,
                },
            ))

        self.assertTrue(result["success"])
        self.assertFalse(result["already_completed"])
        self.assertEqual(
            "구매자에게 인수확인 요청하였습니다.",
            result["website_status"],
        )
        self.assertEqual(1, events.count("resolve-chat"))
        self.assertIn("click:#state5", events)
        self.assertIn(
            "click:#commonAlert .common_alert_check",
            events,
        )

    def test_itembay_delivery_confirmation_uses_seller_detail_button(self):
        events = []
        delivery_selector = (
            ".bay-btn-confirm[onclick*='ItemGiveTake.setGiveItem']"
        )

        class FakeLocator:
            def __init__(self, selector, page):
                self.selector = selector
                self.page = page

            @property
            def first(self):
                return self

            async def wait_for(self, **_kwargs):
                events.append(f"wait-for:{self.selector}")

            async def click(self, **_kwargs):
                events.append(f"click:{self.selector}")
                if self.selector == delivery_selector:
                    self.page.delivered = True
                    self.page.url = (
                        "https://www.itembay.com/scripting/scriptProc?"
                        "url=https%3A%2F%2Fwww.itembay.com%2Fmybay%2Fstatus%2F"
                        "mybayStatusGiveList"
                    )

            async def count(self):
                if self.selector == delivery_selector:
                    return 0 if self.page.delivered else 1
                return 1

            async def is_visible(self):
                if self.selector == delivery_selector:
                    return not self.page.delivered
                return True

        class FakePage:
            def __init__(self):
                self.delivered = False
                self.url = ""

            async def goto(self, url, **_kwargs):
                events.append(f"goto:{url}")
                self.url = url

            async def wait_for_timeout(self, milliseconds):
                events.append(f"wait:{milliseconds}")

            def locator(self, selector):
                return FakeLocator(selector, self)

            def on(self, event, _callback):
                events.append(f"on:{event}")

            async def close(self):
                events.append("close")

        class FakeSession:
            def __init__(self):
                self.page = FakePage()

            def begin_transient_operation(self):
                return True

            async def new_page(self):
                return self.page

            def track_transient_page(self, _page):
                return None

            def untrack_transient_page(self, _page):
                return None

            def end_transient_operation(self):
                return None

        detail_url = (
            "https://www.itembay.com/item/transaction/"
            "transactionGiveTakeDetail?iTranSeq=96388874"
        )
        result = asyncio.run(sender._do_confirm_delivery(
            FakeSession(),
            {
                "type": "confirm_delivery",
                "detail_url": detail_url,
            },
        ))

        self.assertTrue(result["success"])
        self.assertFalse(result["already_completed"])
        self.assertEqual(1, events.count(f"goto:{detail_url}"))
        self.assertIn(f"click:{delivery_selector}", events)
        self.assertNotIn("click:#btnTradeAccept", events)

    def test_delivery_confirmation_accepts_itemmania_stage_five_without_button(self):
        events = []

        class StageLocator:
            def __init__(self, index=None):
                self.index = index

            @property
            def first(self):
                return StageLocator(0)

            async def wait_for(self, **_kwargs):
                return None

            async def count(self):
                return 5

            def nth(self, index):
                return StageLocator(index)

            async def get_attribute(self, name):
                if name == "class":
                    return "caution active" if self.index == 4 else "caution"
                return None

            async def inner_text(self):
                return "판매완료" if self.index == 4 else ""

        class MissingButtonLocator:
            @property
            def first(self):
                return self

            async def wait_for(self, **_kwargs):
                raise AssertionError("已完成订单不应再查找交付按钮")

        class FakePage:
            async def goto(self, url, **_kwargs):
                events.append(f"goto:{url}")

            async def wait_for_timeout(self, _milliseconds):
                return None

            def locator(self, selector):
                if selector == ".caution_list .caution":
                    return StageLocator()
                return MissingButtonLocator()

            def on(self, _event, _callback):
                return None

            async def close(self):
                events.append("close")

        class FakeSession:
            def begin_transient_operation(self):
                return True

            async def new_page(self):
                return FakePage()

            def track_transient_page(self, _page):
                return None

            def untrack_transient_page(self, _page):
                return None

            def end_transient_operation(self):
                return None

        result = asyncio.run(sender._do_confirm_delivery(
            FakeSession(),
            {
                "type": "confirm_delivery",
                "detail_url": "https://www.itemmania.com/order/63",
                "open_confirm_selector": "#trade_btn",
                "confirm_selector": "#delivery-confirm",
                "success_selector": ".caution_list .caution.active p",
                "success_texts": ["인계완료", "판매완료"],
                "stage_selector": ".caution_list .caution",
                "pending_stage": 3,
            },
        ))

        self.assertTrue(result["success"])
        self.assertTrue(result["already_completed"])
        self.assertEqual(5, result["website_stage"])
        self.assertEqual("판매완료", result["website_status"])
        self.assertIn("第 3 阶段", result["message"])
        self.assertEqual(["goto:https://www.itemmania.com/order/63", "close"], events)

    def test_itemmania_delivery_stages_after_three_are_complete(self):
        action = {"pending_stage": 3}

        self.assertFalse(sender._delivery_stage_is_complete(None, action))
        self.assertFalse(sender._delivery_stage_is_complete(3, action))
        self.assertTrue(sender._delivery_stage_is_complete(4, action))
        self.assertTrue(sender._delivery_stage_is_complete(5, action))


if __name__ == "__main__":
    unittest.main()
