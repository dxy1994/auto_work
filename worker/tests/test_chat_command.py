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

    def test_barotem_passes_file_to_imgchg_then_confirms_on_same_page(self):
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

            async def set_input_files(self, _path):
                events.append("imgchg:file-selected")

            async def get_attribute(self, name):
                if (
                    self.selector.startswith("#barotem_imgchg_trigger_")
                    and name == "data-success"
                ):
                    return "true"
                return None

            async def click(self, **_kwargs):
                if self.selector.startswith("#barotem_imgchg_trigger_"):
                    events.append("imgchg:file-argument")
                    self.page.preview_ready = True
                elif self.selector == (
                    '#imgpopup.inline button[onclick="confirmAndSend()"]'
                ):
                    events.append("imgchg:confirm")
                    self.page.sent_count += 1

        class FakePage:
            def __init__(self):
                self.sent_count = 0
                self.preview_ready = False

            def locator(self, selector):
                return FakeLocator(self, selector)

            async def evaluate(self, script, _arg=None):
                if "input.type = 'file'" in script:
                    self.assert_in_memory_imgchg = (
                        "imgchg({" in script
                        and "ClipboardEvent" not in script
                        and "dispatchEvent" not in script
                    )
                    events.append("imgchg:input-created")
                else:
                    events.append("imgchg:controls-removed")

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
        self.assertIn("imgchg:input-created", events)
        self.assertIn("imgchg:file-argument", events)
        self.assertIn("imgchg:confirm", events)
        self.assertTrue(page.assert_in_memory_imgchg)

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
