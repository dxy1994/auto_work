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
    _BarotemHtmlSnapshot,
    _BarotemLoginRequired,
    _BarotemOrderSnapshot,
    _fetch_authenticated_html,
    _fetch_orders_page,
    _handle_blocking_popups,
    _html_requires_login,
    _order_payloads_from_html,
    _order_payloads_from_api,
    _parse_order_card_payload,
    _parse_chat_view_url,
    _parse_product_detail_html,
    _parse_product_view_id,
    _parse_refresh_product_id,
    _resolve_order_quantity,
    _order_list_url,
    _product_list_url,
    _sales_products_page_from_api,
    _sales_products_page_from_html,
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
    @staticmethod
    def _live_card_html(*, order_no="178583752411285073-61"):
        return f"""
          <div class="product_wrap">
            <div class="product_title">
              <h4 class="trading">판매중</h4>
              <time>26년 08월 04일 18:58:47</time>
            </div>
            <input class="product_checkbox" value="{order_no}">
            <div class="product_detail_info"
                 onclick="productview('39182563')">
              <h4><span>리니지 클래식</span> 군터 /</h4>
              <p>빠른 아데나 거래</p>
            </div>
            <div class="product_detail_price">
              <div><h4>수량</h4><h4>10</h4></div>
              <div><h4>가격</h4><h4>9,800 원</h4></div>
            </div>
            <button onclick="dealinfo('encoded', '은하수',
                    '{order_no}', '구매자 정보', 'itme');">buyer</button>
            <button onclick="ycommon.openChat(
                    '/chat/view?jangNum=9161506&gt;', 'chat', '1000', '1000');">
              chat
            </button>
          </div>
        """

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

    def test_background_html_parser_matches_order_and_product_cards(self):
        html = f"""
          <div class="product_background"><div class="product_contents">
            {self._live_card_html()}
          </div></div>
        """

        payloads, card_count = _order_payloads_from_html(
            html, _order_list_url("money"))
        product_html = html.replace(
            'value="178583752411285073-61"',
            'value="39182563"',
            1,
        )
        products = _sales_products_page_from_html(product_html, "money")

        self.assertEqual(1, card_count)
        self.assertEqual("178583752411285073-61", payloads[0]["order_no"])
        self.assertEqual("리니지 클래식", payloads[0]["game_name"])
        self.assertEqual("군터 /", payloads[0]["server"])
        self.assertEqual("은하수", _parse_order_card_payload(
            payloads[0])["buyer_character"])
        self.assertEqual(1, products["total_cards"])
        self.assertEqual(
            "39182563", products["products"][0]["platform_product_id"])

    def test_background_html_parser_accepts_live_empty_order_structure(self):
        html = """
          <div data-item="id">계정 0</div>
          <div data-item="money">게임머니 0</div>
          <div data-item="item">아이템 0</div>
          <div data-item="etc">기타 0</div>
          <div data-item="gift">상품권 0</div>
          <div class="product_background"><div class="product_contents">
          </div></div>
        """

        payloads, card_count = _order_payloads_from_html(
            html, _order_list_url("money"))

        self.assertEqual([], payloads)
        self.assertEqual(0, card_count)

    def test_order_api_parser_matches_deal_list_fields(self):
        payloads, total = _order_payloads_from_api({
            "code": 200,
            "total": "1",
            "rows": [{
                "gou_number": "178583752411285073-61",
                "categoryName": "리니지 클래식",
                "productheader": "군터",
                "title": "24시 아데나 판매",
                "quantityText": "38만 아데나",
                "pay": "30,400",
                "chrName": "은하수",
                "product_number": "38895915",
                "number": "178583752411285073-61",
                "regDate": "26년 08월 07일 15:20:00",
                "product_stats": "4",
            }],
        }, "money")

        self.assertEqual(1, total)
        self.assertEqual("178583752411285073-61", payloads[0]["order_no"])
        self.assertEqual("은하수", payloads[0]["buyer_character"])
        self.assertEqual("38895915", payloads[0]["platform_product_id"])
        self.assertEqual("30,400 원", payloads[0]["price"])

    def test_background_html_parser_rejects_count_card_mismatch(self):
        html = """
          <div data-item="money">게임머니 1</div>
          <div class="product_background"><div class="product_contents">
          </div></div>
        """

        with self.assertRaisesRegex(ValueError, "显示 1 笔"):
            _order_payloads_from_html(html, _order_list_url("money"))

    def test_sales_product_parser_accepts_live_empty_structure(self):
        html = """
          <div data-item="id">계정 0</div>
          <div data-item="money">게임머니 0</div>
          <div data-item="item">아이템 0</div>
          <div data-item="etc">기타 0</div>
          <div data-item="gift">상품권 0</div>
          <div class="product_background"><div class="product_contents">
          </div></div>
        """

        result = _sales_products_page_from_html(html, "item")

        self.assertEqual({"total_cards": 0, "products": []}, result)

    def test_sales_product_parser_rejects_count_card_mismatch(self):
        html = """
          <div data-item="money">게임머니 3</div>
          <div class="product_background"><div class="product_contents">
          </div></div>
        """

        with self.assertRaisesRegex(ValueError, "显示 3 个"):
            _sales_products_page_from_html(html, "money")

    def test_sales_product_api_parser_matches_live_response_fields(self):
        result = _sales_products_page_from_api({
            "code": 200,
            "total": "3",
            "rows": [{
                "number": "38895915",
                "itemtype": "money",
                "categoryName": "리니지 클래식",
                "productheader": "군터",
                "product_name": "24시 아데나 판매",
                "quantityText": "38만 아데나",
                "baro_price": "800 원",
                "regDate": "26년 08월 07일 15:18:52",
                "product_stats": "0",
            }],
        }, "money")

        self.assertEqual(3, result["total"])
        self.assertEqual(1, result["total_cards"])
        self.assertEqual("38895915", result["products"][0][
            "platform_product_id"])
        self.assertEqual("리니지 클래식", result["products"][0][
            "game_name"])
        self.assertEqual("군터", result["products"][0]["region_name"])

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

    async def test_background_order_poll_does_not_reload_long_lived_page(self):
        worker, page = self._order_worker()
        worker._monitor._collect_and_report_orders = AsyncMock(return_value=0)
        html = """
          <div data-item="id">계정 0</div>
          <div data-item="money">게임머니 0</div>
          <div data-item="item">아이템 0</div>
          <div data-item="etc">기타 0</div>
          <div data-item="gift">상품권 0</div>
          <div class="product_background"><div class="product_contents">
          </div></div>
        """
        snapshot = _BarotemHtmlSnapshot(
            _order_list_url("money"), html, None)

        with patch.object(
                barotem_module, "_fetch_authenticated_html",
                AsyncMock(return_value=snapshot)) as fetch:
            reported = await worker._collect_all_order_categories(10000)

        self.assertEqual(0, reported)
        fetch.assert_awaited_once_with(
            page, _order_list_url("money"), 10000)
        worker._monitor._collect_and_report_orders.assert_not_awaited()
        page.reload.assert_not_awaited()
        page.goto.assert_not_awaited()

    async def test_background_login_redirect_uses_controlled_recovery(self):
        worker, page = self._order_worker()
        worker._goto_business_page = AsyncMock(return_value=False)
        worker._recover_login_if_needed = AsyncMock(return_value=True)

        recovered = await worker._recover_after_background_login_required(
            ORDER_LIST_URL,
            ORDER_CONTENT_SELECTOR,
            10000,
            reason="后台请求测试",
        )

        self.assertTrue(recovered)
        worker._goto_business_page.assert_awaited_once()
        worker._recover_login_if_needed.assert_awaited_once()
        page.reload.assert_not_awaited()

    async def test_background_request_reports_login_redirect(self):
        response = SimpleNamespace(
            url="https://www.barotem.com/auth/login",
            ok=True,
            status=200,
            text=AsyncMock(),
        )
        request = SimpleNamespace(get=AsyncMock(return_value=response))
        page = SimpleNamespace(context=SimpleNamespace(request=request))

        with self.assertRaises(_BarotemLoginRequired):
            await _fetch_authenticated_html(
                page, _order_list_url("money"), 10000)

        response.text.assert_not_awaited()

    async def test_background_request_detects_http_200_login_alert(self):
        html = """
          <article id="commonAlert" class="common_alert"
                   style="display: flex;">
            <h2>로그인 후 이용가능합니다.</h2>
            <button class="common_alert_check"
                    onclick='location.href = "/auth/login";'>확인</button>
          </article>
        """
        response = SimpleNamespace(
            url=_order_list_url("money"),
            ok=True,
            status=200,
            text=AsyncMock(return_value=html),
        )
        request = SimpleNamespace(get=AsyncMock(return_value=response))
        page = SimpleNamespace(context=SimpleNamespace(request=request))

        self.assertTrue(_html_requires_login(html))
        self.assertFalse(_html_requires_login(
            html.replace("display: flex", "display: none")))
        with self.assertRaises(_BarotemLoginRequired):
            await _fetch_authenticated_html(
                page, _order_list_url("money"), 10000)

        response.text.assert_awaited_once()

    async def test_monitor_extracts_orders_from_background_snapshot(self):
        monitor = object.__new__(BarotemMonitor)
        monitor._session = SimpleNamespace(
            remember_conversation_url=MagicMock())
        monitor._get_product_detail = AsyncMock(return_value={
            "detail_server": "군터",
            "minimum_quantity": "10만 아데나",
            "maximum_quantity": "9,666만 아데나",
            "detail_price": "만 아데나당 980원",
        })
        html = f"""
          <div class="product_background"><div class="product_contents">
            {BarotemStructureTest._live_card_html()}
          </div></div>
        """
        snapshot = _BarotemHtmlSnapshot(
            _order_list_url("money"), html, None)

        result = await monitor._extract_orders_from_table(snapshot)

        self.assertFalse(result.failed)
        self.assertEqual(1, len(result.orders))
        self.assertEqual(
            "178583752411285073-61", result.orders[0]["order_no"])
        monitor._get_product_detail.assert_awaited_once_with(
            snapshot, "39182563")
        monitor._session.remember_conversation_url.assert_called_once()

    async def test_order_api_snapshot_keeps_collect_business_url(self):
        monitor = object.__new__(BarotemMonitor)
        response = SimpleNamespace(
            url="https://www.barotem.com/mypage/DealList",
            ok=True,
            status=200,
            text=AsyncMock(return_value=(
                '{"code":200,"total":"0","rows":[]}')),
        )
        request = SimpleNamespace(
            post=AsyncMock(return_value=response))
        page = SimpleNamespace(
            context=SimpleNamespace(request=request))

        snapshot = await _fetch_orders_page(page, "money", 1, 10000)

        self.assertTrue(monitor._is_on_collect_page(snapshot))
        self.assertEqual(_order_list_url("money"), snapshot.url)

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

    async def test_product_snapshot_uses_json_api_without_navigation(self):
        monitor = SimpleNamespace(
            post_login_check=AsyncMock(return_value=False),
        )
        worker = BarotemRefreshWorker(_FakeSession(), None, monitor)
        page = SimpleNamespace(
            reload=AsyncMock(),
            goto=AsyncMock(),
        )
        worker._page = page
        async def fetch_page(_page, item_type, _page_number, _timeout):
            if item_type != "money":
                return {"total": 0, "total_cards": 0, "products": []}
            return {
                "total": 1,
                "total_cards": 1,
                "products": [{"platform_product_id": "39182563"}],
            }

        with patch.object(
                barotem_module, "_fetch_sales_products_page",
                AsyncMock(side_effect=fetch_page)) as fetch:
            products = await worker._collect_sales_products_snapshot(10000)

        self.assertEqual(["39182563"], [
            product["platform_product_id"] for product in products
        ])
        self.assertEqual(5, fetch.await_count)
        fetch.assert_any_await(page, "money", 1, 10000)
        page.reload.assert_not_awaited()
        page.goto.assert_not_awaited()

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
        worker._prepare_refresh_action_page.assert_not_awaited()
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
        worker._monitor._collect_and_report_orders = AsyncMock(
            side_effect=[1, 2])
        counts_html = """
          <div data-item="id">계정 0</div>
          <div data-item="money">게임머니 2</div>
          <div data-item="item">아이템 1</div>
          <div data-item="etc">기타 0</div>
          <div data-item="gift">상품권 0</div>
          <div class="product_background"><div class="product_contents">
            <div class="product_empty"></div>
          </div></div>
        """
        snapshots = [
            _BarotemOrderSnapshot(
                "https://www.barotem.com/mypage/DealList",
                [{"order_no": "1-1"}], 2, None),
            _BarotemOrderSnapshot(
                "https://www.barotem.com/mypage/DealList",
                [{"order_no": "2-1"}], 1, None),
        ]

        with patch.object(
                barotem_module, "_fetch_authenticated_html",
                AsyncMock(return_value=_BarotemHtmlSnapshot(
                    _order_list_url("money"), counts_html, None))) as probe:
            with patch.object(
                    barotem_module, "_fetch_orders_page",
                    AsyncMock(side_effect=snapshots)) as fetch:
                reported = await worker._collect_all_order_categories(10000)

        self.assertEqual(3, reported)
        self.assertEqual(2, fetch.await_count)
        probe.assert_awaited_once_with(
            page, _order_list_url("money"), 10000)
        self.assertEqual(
            2, worker._monitor._collect_and_report_orders.await_count)
        page.reload.assert_not_awaited()
        page.goto.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
