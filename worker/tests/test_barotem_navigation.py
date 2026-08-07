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
    LOGIN_ALERT_SELECTOR,
    NEW_CHAT_ALERT_SELECTOR,
    ORDER_CONTENT_SELECTOR,
    ORDER_LIST_URL,
    SELL_LIST_URL,
    TRADE_VERIFICATION_SELECTOR,
    _handle_blocking_popups,
    _parse_order_card_payload,
    _parse_chat_view_url,
    _parse_product_detail_html,
    _parse_product_view_id,
    _parse_refresh_product_id,
    _resolve_order_quantity,
    _order_list_url,
    _product_list_url,
)
from monitor.orders.adapters import adapter_for  # noqa: E402


class _FakeSession:
    account_id = 7

    @staticmethod
    def is_login_page(_url):
        return False


class _PopupLocator:
    def __init__(self, *, name="", count=1, visible=True, text="",
                 events=None, children=None, on_click=None):
        self.name = name
        self._count = count
        self._visible = visible
        self._text = text
        self._events = events if events is not None else []
        self._children = children if children is not None else {}
        self._on_click = on_click
        self._value = ""
        self._checked = False

    @property
    def first(self):
        return self

    @property
    def last(self):
        return self

    def locator(self, selector):
        return self._children.get(
            selector,
            _PopupLocator(count=0, visible=False, events=self._events),
        )

    async def count(self):
        return self._count

    async def is_visible(self):
        return self._visible

    async def inner_text(self):
        return self._text

    async def click(self, **_kwargs):
        self._events.append(f"click:{self.name}")
        if self._on_click is not None:
            self._on_click()

    async def wait_for(self, **kwargs):
        self._events.append(f"wait:{self.name}:{kwargs.get('state')}")

    async def fill(self, value, **_kwargs):
        self._value = value
        self._events.append(f"fill:{self.name}:{value}")

    async def check(self, **_kwargs):
        self._checked = True
        self._events.append(f"check:{self.name}")

    async def input_value(self):
        return self._value

    async def is_checked(self):
        return self._checked


class _PopupPage:
    def __init__(self, roots):
        self._roots = roots

    def locator(self, selector):
        return self._roots.get(
            selector,
            _PopupLocator(count=0, visible=False),
        )


def _make_popup_page(*, chat=False, verification=False):
    events = []
    roots = {}
    if chat:
        chat_title = _PopupLocator(
            name="chat-title", text="신규 채팅 알림", events=events)
        chat_close = _PopupLocator(name="chat-close", events=events)
        roots[NEW_CHAT_ALERT_SELECTOR] = _PopupLocator(
            name="chat-modal",
            events=events,
            children={
                "h2": chat_title,
                ".charge_modal_close": chat_close,
            },
        )
    if verification:
        heading = _PopupLocator(
            name="trade-title", text="안전 거래 정보 확인", events=events)
        character = _PopupLocator(
            name="character", text="은하수", events=events)
        input_box = _PopupLocator(name="character-input", events=events)
        checkbox = _PopupLocator(name="risk-checkbox", events=events)
        checkbox_label = _PopupLocator(
            name="risk-label",
            events=events,
            on_click=lambda: setattr(checkbox, "_checked", True),
        )
        confirm = _PopupLocator(name="trade-confirm", events=events)
        roots[TRADE_VERIFICATION_SELECTOR] = _PopupLocator(
            name="trade-modal",
            events=events,
            children={
                ".prevention_modal_wrap > h2": heading,
                ".chrInfo:visible .chrname": character,
                "#chrCheck:visible": input_box,
                "#payment_alert_chrCheck": checkbox,
                "label[for='payment_alert_chrCheck']:visible": checkbox_label,
                (
                    ".btns_wrap.sellerChk:visible "
                    ".success[onclick*='preventionchrCheck']"
                ): confirm,
            },
        )
    return _PopupPage(roots), events


class BarotemPopupTest(unittest.IsolatedAsyncioTestCase):
    async def test_new_chat_alert_can_appear_alone(self):
        page, events = _make_popup_page(chat=True)

        handled = await _handle_blocking_popups(page)

        self.assertEqual(["new_chat_alert"], handled)
        self.assertEqual(
            ["click:chat-close", "wait:chat-modal:hidden"],
            events,
        )

    async def test_trade_verification_can_appear_alone(self):
        page, events = _make_popup_page(verification=True)

        handled = await _handle_blocking_popups(page)

        self.assertEqual(["trade_verification"], handled)
        self.assertEqual([
            "fill:character-input:은하수",
            "click:risk-label",
            "click:trade-confirm",
            "wait:trade-modal:hidden",
        ], events)

    async def test_new_chat_alert_is_closed_before_trade_verification(self):
        page, events = _make_popup_page(chat=True, verification=True)

        handled = await _handle_blocking_popups(page)

        self.assertEqual(
            ["new_chat_alert", "trade_verification"],
            handled,
        )
        self.assertLess(
            events.index("click:chat-close"),
            events.index("fill:character-input:은하수"),
        )

    async def test_popups_can_appear_in_separate_checks(self):
        chat_page, _events = _make_popup_page(chat=True)
        verification_page, _events = _make_popup_page(verification=True)

        first = await _handle_blocking_popups(chat_page)
        second = await _handle_blocking_popups(verification_page)

        self.assertEqual(["new_chat_alert"], first)
        self.assertEqual(["trade_verification"], second)


class BarotemStructureTest(unittest.TestCase):
    def test_chat_url_parser_removes_live_onclick_trailing_marker(self):
        self.assertEqual(
            "https://www.barotem.com/chat/view?jangNum=9161506",
            _parse_chat_view_url(
                "ycommon.openChat('/chat/view?jangNum=9161506>', "
                "'happy_chating_mypage','1000','1000');"
            ),
        )

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

    def test_live_lineage_order_uses_product_detail_quantity_unit(self):
        detail = _parse_product_detail_html("""
            <ul>
              <li class="info"><p>서버</p><div>군터</div></li>
              <li class="info"><p>최소수량</p><div>10만 아데나</div></li>
              <li class="info"><p>최대수량</p><div>9,666만 아데나</div></li>
              <li class="info"><p>상세가격</p><div>만 아데나당 980원</div></li>
            </ul>
        """)
        product_id = _parse_product_view_id("productview('39182563')")
        parsed = _parse_order_card_payload({
            "order_no": "178583752411285073-61",
            "game_name": "리니지 클래식",
            "server": "군터 /",
            "title": "❤️█❤️%아데나%❤️█❤️24시 -안전거래--❤️❤️빠른거래",
            "amount": "10",
            "price": "9,800 원",
            "buyer_onclick": (
                "dealinfo('106 121 122 49 48 50 55 ', '은하수', "
                "'178583752411285073-61', '구매자 정보', 'itme');"
            ),
            "order_time": "26년 08월 04일 18:58:47",
            "mode": "4",
            "item_type": "money",
            "platform_product_id": product_id,
            **detail,
        })

        quantity = _resolve_order_quantity(
            parsed["amount"],
            parsed["detail_price"],
            parsed["minimum_quantity"],
            require_detail=True,
        )
        normalized = asyncio.run(
            BarotemMonitor._build_normalized_order(
                object.__new__(BarotemMonitor), None, parsed
            )
        )

        self.assertEqual("39182563", parsed["platform_product_id"])
        self.assertEqual("군터", detail["detail_server"])
        self.assertEqual(100000, quantity)
        self.assertIsNotNone(normalized)
        self.assertEqual(100000, normalized.asset_amount)
        self.assertEqual(100000, normalized.quantity)
        self.assertEqual(100000, normalized.sale_quantity)

    def test_plain_item_quantity_keeps_list_value_without_detail(self):
        self.assertEqual(
            3,
            _resolve_order_quantity("3", require_detail=False),
        )

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

        alert = AsyncMock()
        with patch.object(
            barotem_module, "play_alert_audio_async", alert
        ):
            ready = await worker._ensure_order_page_ready(10000)

        self.assertTrue(ready)
        alert.assert_awaited_once_with(
            text="barotem账号7登录已失效，正在自动重新登录"
        )
        session.relogin.assert_awaited_once_with(page)
        page.goto.assert_awaited_once()
        self.assertEqual(ORDER_LIST_URL, page.goto.await_args.args[0])

    async def test_login_check_only_reads_visible_common_alert(self):
        check = SimpleNamespace(
            get_attribute=AsyncMock(return_value="go('/auth/login')"),
        )
        checks = SimpleNamespace(
            count=AsyncMock(return_value=1),
            nth=MagicMock(return_value=check),
        )
        page = SimpleNamespace(
            locator=MagicMock(return_value=checks),
        )
        monitor = SimpleNamespace(_log_tag="BarotemTest")

        required = await BarotemMonitor.post_login_check(monitor, page)

        self.assertTrue(required)
        page.locator.assert_called_once_with(LOGIN_ALERT_SELECTOR)
        self.assertIn(":visible", LOGIN_ALERT_SELECTOR)

    async def test_relogin_alert_is_shared_between_workers_and_repeats(self):
        session = SimpleNamespace(account_id=7)
        monitor = SimpleNamespace(
            post_login_check=AsyncMock(return_value=True),
        )
        order_worker = BarotemOrderWorker(session, None, monitor)
        refresh_worker = BarotemRefreshWorker(session, None, monitor)
        alert = AsyncMock()

        with (
            patch.object(
                barotem_module, "RELOGIN_ALERT_INTERVAL_SECONDS", 0.01
            ),
            patch.object(barotem_module, "play_alert_audio_async", alert),
        ):
            await order_worker._start_relogin_alerts()
            await refresh_worker._start_relogin_alerts()
            await asyncio.sleep(0.025)
            self.assertTrue(session._barotem_relogin_alert_active)
            self.assertGreaterEqual(alert.await_count, 2)
            await order_worker._stop_relogin_alerts()

        self.assertEqual(
            "barotem账号7登录已失效，正在自动重新登录",
            alert.await_args_list[0].kwargs["text"],
        )
        self.assertIn(
            "登录已失效，请完成登录验证",
            alert.await_args_list[1].kwargs["text"],
        )
        self.assertFalse(session._barotem_relogin_alert_active)

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

    async def test_scheduled_product_refresh_is_disabled_but_snapshot_remains(self):
        monitor = SimpleNamespace(
            post_login_check=AsyncMock(return_value=False),
        )
        worker = BarotemRefreshWorker(_FakeSession(), None, monitor)
        worker._prepare_refresh_action_page = AsyncMock()
        worker._sync_sales_products = AsyncMock(return_value={"success": True})
        worker._do_refresh = AsyncMock(return_value="refreshed")

        with patch.object(
                barotem_module,
                "SCHEDULED_PRODUCT_REFRESH_ENABLED",
                False):
            result = await worker._run_refresh_cycle(10000)

        self.assertEqual("scheduled_refresh_disabled", result)
        worker._prepare_refresh_action_page.assert_awaited_once_with(10000)
        worker._sync_sales_products.assert_awaited_once_with(10000)
        worker._do_refresh.assert_not_awaited()

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
