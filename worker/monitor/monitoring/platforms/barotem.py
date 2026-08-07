"""
Barotem 订单监控（Async 多页面并行架构）。

Worker 分工：
  - BarotemOrderWorker：固定在销售中页面，刷新、提取并上报订单
  - BarotemRefreshWorker：固定在上架列表，轮换商品分类并执行「끌어올리기」
"""

import asyncio
import datetime
import re
import time
from decimal import Decimal
from typing import List, Optional
from urllib.parse import urlencode, urljoin, urlparse, parse_qs

from bs4 import BeautifulSoup

from monitor.browser.audio import play_alert_audio_async
from monitor.monitoring.base import BaseOrderMonitor
from monitor.monitoring.extraction import OrderExtractionResult
from monitor.monitoring.worker import PageWorker
from monitor.orders.adapters import adapter_for, parse_korean_amount


SELL_LIST_URL = "https://www.barotem.com/mypage/sellingproduct/sell"
ORDER_LIST_URL = "https://www.barotem.com/mypage/sellview/4"
PRODUCT_DETAIL_URL = "https://www.barotem.com/product/view/{product_id}"

NEW_CHAT_ALERT_SELECTOR = "#chargeModal:visible"
TRADE_VERIFICATION_SELECTOR = ".preventionground:visible"
LOGIN_ALERT_SELECTOR = "#commonAlert:visible .common_alert_check:visible"
POPUP_ACTION_TIMEOUT_MS = 5000

ORDER_CONTENT_SELECTOR = ".product_background .product_contents"
ORDER_CARD_SELECTOR = ".product_contents .product_wrap"
REFRESH_CONTENT_SELECTOR = ".product_background .product_contents"
REFRESH_CARD_SELECTOR = ".product_contents .product_wrap"
REFRESH_BUTTON_SELECTOR = '[onclick^="reregister("]'
REFRESH_CONFIRM_SELECTOR = ".common_alert_check"

PRODUCT_TYPES = ("money", "item", "id", "etc", "gift")
PRODUCT_PAGE_SIZE = 500
MIN_COMMIT_TIMEOUT_MS = 15000
MIN_READY_TIMEOUT_MS = 20000
COMMIT_GRACE_SECONDS = 3.0
REFRESH_RESULT_TIMEOUT_SECONDS = 15.0
REFRESH_PAGE_MAX_ACTIONS = 30
SCHEDULED_PRODUCT_REFRESH_ENABLED = False
RELOGIN_MAX_ATTEMPTS = 3
RELOGIN_BACKOFF_SECONDS = (30.0, 120.0)
RELOGIN_ALERT_INTERVAL_SECONDS = 3.0


def _compact_text(value) -> str:
    return " ".join(str(value or "").split())


def _parse_buyer_character(onclick: str) -> str:
    """从 dealinfo(userid, character, order, ...) 中读取买家角色名。"""
    match = re.search(r"\bdealinfo\s*\((?P<args>.*)\)\s*;?\s*$",
                      str(onclick or ""), re.DOTALL)
    if not match:
        return ""
    quoted = re.findall(r"""(['"])(.*?)\1""", match.group("args"),
                        re.DOTALL)
    return _compact_text(quoted[1][1]) if len(quoted) >= 2 else ""


def _parse_product_view_id(onclick: str) -> str:
    """从 productview(product_id) 中读取订单对应的在售商品 ID。"""
    match = re.search(
        r"\bproductview\s*\(\s*['\"]?(\d+)",
        str(onclick or ""),
    )
    return match.group(1) if match else ""


def _parse_chat_view_url(onclick: str) -> str:
    """从订单卡片提取聊天入口，并去掉站点 onclick 中多余的 ``>``。"""
    match = re.search(
        r"(?P<path>/chat/view\?jangNum=\d+)",
        str(onclick or ""),
    )
    if not match:
        return ""
    chat_url = urljoin("https://www.barotem.com", match.group("path"))
    parsed = urlparse(chat_url)
    if (
        (parsed.hostname or "").lower()
        not in {"barotem.com", "www.barotem.com"}
        or parsed.path.rstrip("/") != "/chat/view"
    ):
        return ""
    return chat_url


def _parse_product_detail_html(html: str) -> dict:
    """读取商品详情页中决定订单实际数量单位的字段。"""
    soup = BeautifulSoup(str(html or ""), "html.parser")
    labels = {
        "서버": "detail_server",
        "최소수량": "minimum_quantity",
        "최대수량": "maximum_quantity",
        "상세가격": "detail_price",
    }
    result = {}
    for item in soup.select("li.info"):
        label_node = item.find("p", recursive=False)
        if label_node is None:
            continue
        key = labels.get(_compact_text(label_node.get_text(" ", strip=True)))
        if not key:
            continue
        value_node = next(
            (
                child
                for child in item.find_all(recursive=False)
                if getattr(child, "name", None) and child is not label_node
            ),
            None,
        )
        value = _compact_text(
            value_node.get_text(" ", strip=True) if value_node else ""
        )
        if value:
            result[key] = value
    return result


def _detail_quantity_scale(detail_price: str) -> Optional[Decimal]:
    """从“만 아데나당 980원”等详情价格中提取每个列表单位的实际数量。"""
    text = _compact_text(detail_price)
    if "당" not in text:
        return None
    unit_text = text.split("당", 1)[0]
    match = re.search(
        r"(?P<amount>(?:\d[\d,]*)?\s*(?:조|억|만|천|백|십))",
        unit_text,
    )
    if not match:
        return Decimal("1")
    amount_text = match.group("amount")
    if not re.search(r"\d", amount_text):
        amount_text = "1" + amount_text
    return parse_korean_amount(amount_text)


def _resolve_order_quantity(
        amount: str, detail_price: str = "",
        minimum_quantity: str = "", require_detail: bool = False) -> Decimal:
    """把列表的购买单位数换算为游戏内真实数量。"""
    amount_text = _compact_text(amount)
    base_amount = parse_korean_amount(amount_text)
    if re.search(r"(?:조|억|만|천|백|십)", amount_text):
        return base_amount

    scale = _detail_quantity_scale(detail_price)
    if scale is None and minimum_quantity:
        minimum_total = parse_korean_amount(minimum_quantity)
        number_match = re.search(r"\d+(?:,\d{3})*(?:\.\d+)?", minimum_quantity)
        if number_match:
            minimum_units = Decimal(number_match.group(0).replace(",", ""))
            if minimum_units > 0:
                scale = minimum_total / minimum_units
    if scale is None:
        if require_detail:
            raise ValueError("未读取到 Barotem 商品数量单位")
        scale = Decimal("1")
    quantity = base_amount * scale
    if quantity != quantity.to_integral_value():
        raise ValueError("Barotem 订单实际数量不是整数")
    return quantity


def _parse_order_card_payload(payload: dict) -> Optional[dict]:
    """把浏览器一次性读取的 Barotem 订单卡片转成平台原始订单。"""
    order_no = _compact_text(payload.get("order_no"))
    if not re.fullmatch(r"\d+-\d+", order_no):
        raise ValueError("未提取到 Barotem 完整交易号")

    game_name = _compact_text(payload.get("game_name"))
    server = _compact_text(payload.get("server")).rstrip("/").strip()
    title = _compact_text(payload.get("title"))
    amount = _compact_text(payload.get("amount"))
    buyer = _parse_buyer_character(payload.get("buyer_onclick", ""))
    if not game_name or not server:
        raise ValueError("未提取到游戏或区服")
    if not title:
        raise ValueError("未提取到商品标题")
    if not amount:
        raise ValueError("未提取到交易数量")
    if not buyer:
        raise ValueError("未提取到买家角色名")

    mode = _compact_text(payload.get("mode"))
    if mode == "4":
        status = "trading"
    elif mode == "5":
        status = "completed"
    else:
        status = _compact_text(payload.get("status")) or "trading"

    return {
        "order_no": order_no,
        "deal_id": order_no,
        "platform_product_id": _compact_text(
            payload.get("platform_product_id")),
        "game_name": game_name,
        "server_code": server,
        "item_type": _compact_text(payload.get("item_type")) or "unknown",
        "item_name": title,
        "amount": amount,
        "price": _compact_text(payload.get("price")),
        "buyer_character": buyer,
        "platform_order_time": _compact_text(payload.get("order_time")),
        "minimum_quantity": _compact_text(payload.get("minimum_quantity")),
        "maximum_quantity": _compact_text(payload.get("maximum_quantity")),
        "detail_price": _compact_text(payload.get("detail_price")),
        "status": status,
        "state": status,
    }


def _parse_refresh_product_id(onclick: str) -> str:
    match = re.search(r"\breregister\s*\(\s*['\"]?(\d+)",
                      str(onclick or ""))
    return match.group(1) if match else ""


def _parse_sales_product_card_payload(
        payload: dict, item_type: str) -> dict:
    """把 Barotem 在售商品卡片转成快照协议字段。"""
    product_id = _compact_text(payload.get("platform_product_id"))
    if not re.fullmatch(r"\d+", product_id):
        raise ValueError("未提取到有效的 Barotem 商品 ID")
    return {
        "platform_product_id": product_id,
        "platform_item_type": _compact_text(item_type),
        "game_name": _compact_text(payload.get("game_name")),
        "region_name": _compact_text(
            payload.get("region_name")).rstrip("/").strip(),
        "title": _compact_text(payload.get("title")),
        "quantity_text": _compact_text(payload.get("quantity_text")),
        "price_text": _compact_text(payload.get("price_text")),
        "platform_registered_at": _compact_text(
            payload.get("platform_registered_at")),
    }


def _product_list_url(item_type: str, page: int = 1) -> str:
    query = urlencode({
        "mode": "0",
        "itemtype": item_type,
        "page": str(page),
        "orderby": "reg_date",
        "limit": str(PRODUCT_PAGE_SIZE),
    })
    return f"{SELL_LIST_URL}?{query}"


def _order_list_url(item_type: str) -> str:
    query = urlencode({
        "mode": "4",
        "itemtype": item_type,
        "page": "1",
        "orderby": "reg_date",
        "limit": "500",
    })
    return f"{ORDER_LIST_URL}?{query}"


async def _fetch_product_detail(page, product_id: str) -> dict:
    """通过当前登录上下文读取商品详情，不离开订单列表页面。"""
    if not re.fullmatch(r"\d+", str(product_id or "")):
        raise ValueError("Barotem 商品 ID 无效")
    url = PRODUCT_DETAIL_URL.format(product_id=product_id)
    response = await page.context.request.get(url, timeout=10000)
    if not response.ok:
        raise RuntimeError(
            f"Barotem 商品详情请求失败: HTTP {response.status}"
        )
    response_url = str(response.url or "")
    if "/auth/login" in response_url:
        raise RuntimeError("Barotem 商品详情请求被重定向到登录页")
    detail = _parse_product_detail_html(await response.text())
    if not detail:
        raise RuntimeError("Barotem 商品详情页未包含数量单位字段")
    return detail


async def _dismiss_new_chat_alert(
        page, timeout: int = POPUP_ACTION_TIMEOUT_MS) -> bool:
    """关闭最上层的新聊天提醒，但不勾选“下次登录前不再显示”。"""
    modal = page.locator(NEW_CHAT_ALERT_SELECTOR).last
    if await modal.count() == 0 or not await modal.is_visible():
        return False

    title = modal.locator("h2").first
    title_text = (
        _compact_text(await title.inner_text())
        if await title.count() > 0 else ""
    )
    if title_text != "신규 채팅 알림":
        return False

    close = modal.locator(".charge_modal_close").last
    if await close.count() == 0 or not await close.is_visible():
        raise RuntimeError("Barotem 新聊天提醒缺少可见的取消按钮")
    await close.click(timeout=timeout)
    await modal.wait_for(state="hidden", timeout=timeout)
    return True


async def _complete_trade_verification(
        page, timeout: int = POPUP_ACTION_TIMEOUT_MS) -> bool:
    """按页面展示的买家角色名完成安全交易确认。"""
    modal = page.locator(TRADE_VERIFICATION_SELECTOR).last
    if await modal.count() == 0 or not await modal.is_visible():
        return False

    heading = modal.locator(".prevention_modal_wrap > h2").first
    heading_text = (
        _compact_text(await heading.inner_text())
        if await heading.count() > 0 else ""
    )
    if heading_text != "안전 거래 정보 확인":
        return False

    character = modal.locator(".chrInfo:visible .chrname").first
    character_name = (
        _compact_text(await character.inner_text())
        if await character.count() > 0 else ""
    )
    input_box = modal.locator("#chrCheck:visible").first
    checkbox = modal.locator("#payment_alert_chrCheck").first
    checkbox_label = modal.locator(
        "label[for='payment_alert_chrCheck']:visible"
    ).first
    confirm = modal.locator(
        ".btns_wrap.sellerChk:visible "
        ".success[onclick*='preventionchrCheck']"
    ).last
    if not character_name:
        return False
    for control in (input_box, checkbox_label, confirm):
        if await control.count() == 0 or not await control.is_visible():
            return False
    if await checkbox.count() == 0:
        return False

    await input_box.fill(character_name, timeout=timeout)
    await checkbox_label.click(timeout=timeout)
    if not await checkbox.is_checked():
        await checkbox.check(timeout=timeout, force=True)
    if _compact_text(await input_box.input_value()) != character_name:
        raise RuntimeError("Barotem 安全交易角色名填写后校验失败")
    if not await checkbox.is_checked():
        raise RuntimeError("Barotem 安全交易风险确认未勾选")

    await confirm.click(timeout=timeout)
    await modal.wait_for(state="hidden", timeout=timeout)
    return True


async def _handle_blocking_popups(
        page, timeout: int = POPUP_ACTION_TIMEOUT_MS) -> List[str]:
    """独立处理可能单独或叠加出现的 Barotem 业务弹窗。"""
    handled = []
    if await _dismiss_new_chat_alert(page, timeout):
        handled.append("new_chat_alert")
    if await _complete_trade_verification(page, timeout):
        handled.append("trade_verification")
    return handled


async def _read_document_time_origin(page) -> Optional[float]:
    try:
        return float(await page.evaluate("performance.timeOrigin"))
    except Exception:
        return None


async def _wait_for_document_change(
        page, previous_origin: Optional[float]) -> bool:
    if previous_origin is None:
        return False
    deadline = asyncio.get_running_loop().time() + COMMIT_GRACE_SECONDS
    while asyncio.get_running_loop().time() < deadline:
        current_origin = await _read_document_time_origin(page)
        if current_origin is not None and current_origin != previous_origin:
            return True
        await asyncio.sleep(0.25)
    return False


class _BarotemWorker(PageWorker):
    """Barotem 两个 Worker 共用的导航和登录恢复逻辑。"""

    def __init__(self, session, stop_event, monitor: 'BarotemMonitor',
                 name: str):
        super().__init__(session, stop_event, name=name)
        self._monitor = monitor
        self._relogin_failures = 0
        self._next_relogin_at = 0.0
        self._relogin_disabled = False
        self._last_relogin_wait_log_at = 0.0

    async def _handle_page_popups(self) -> List[str]:
        if not callable(getattr(self.page, "locator", None)):
            return []
        try:
            handled = await _handle_blocking_popups(self.page)
        except Exception as exc:
            print(f"[{self._log_tag}] Barotem 弹窗自动处理失败: {exc}")
            return []
        if handled:
            print(f"[{self._log_tag}] 已自动处理页面弹窗: "
                  f"{', '.join(handled)}")
        return handled

    async def on_stop(self):
        await self._stop_relogin_alerts()

    async def _login_required(self) -> bool:
        await self._handle_page_popups()
        if self._session.is_login_page(self.page.url):
            return True
        return await self._monitor.post_login_check(self.page)

    async def _start_relogin_alerts(self) -> None:
        """登录恢复期间每 3 秒持续播报；同账号多个 Worker 共用一个任务。"""
        if getattr(self._session, "_barotem_relogin_alert_active", False):
            return
        # 在第一次 await 前置位，避免订单页和商品页同时启动两套播报。
        setattr(self._session, "_barotem_relogin_alert_active", True)
        await play_alert_audio_async(
            text=(f"barotem账号{self._session.account_id}登录已失效，"
                  "正在自动重新登录")
        )

        async def _repeat():
            try:
                while getattr(
                        self._session,
                        "_barotem_relogin_alert_active",
                        False):
                    await asyncio.sleep(RELOGIN_ALERT_INTERVAL_SECONDS)
                    if not getattr(
                            self._session,
                            "_barotem_relogin_alert_active",
                            False):
                        break
                    await play_alert_audio_async(
                        text=(
                            f"barotem账号{self._session.account_id}"
                            "登录已失效，请完成登录验证"
                        )
                    )
            except asyncio.CancelledError:
                return

        task = asyncio.create_task(_repeat())
        setattr(self._session, "_barotem_relogin_alert_task", task)

    async def _stop_relogin_alerts(self) -> None:
        """业务页确认恢复后立即停止登录提醒。"""
        setattr(self._session, "_barotem_relogin_alert_active", False)
        task = getattr(self._session, "_barotem_relogin_alert_task", None)
        setattr(self._session, "_barotem_relogin_alert_task", None)
        if task is None or task.done():
            return
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    async def _recover_login_if_needed(
            self, target_url: str, ready_selector: str,
            wait_timeout: int, reason: str) -> Optional[bool]:
        """None=无需恢复，True=已恢复，False=退避或等待人工处理。"""
        if not await self._login_required():
            await self._stop_relogin_alerts()
            if self._relogin_failures or self._relogin_disabled:
                print(f"[{self._log_tag}] 已恢复业务页面，清除重新登录退避状态")
                self._relogin_failures = 0
                self._next_relogin_at = 0.0
                self._relogin_disabled = False
            return None

        await self._start_relogin_alerts()
        now = time.monotonic()
        if self._relogin_disabled:
            if now - self._last_relogin_wait_log_at >= 60:
                print(f"[{self._log_tag}] 自动重新登录已暂停，等待人工登录或重启监控")
                self._last_relogin_wait_log_at = now
            return False
        if now < self._next_relogin_at:
            if now - self._last_relogin_wait_log_at >= 15:
                remaining = max(1, int(self._next_relogin_at - now))
                print(f"[{self._log_tag}] 自动重新登录退避中，"
                      f"{remaining} 秒后再试")
                self._last_relogin_wait_log_at = now
            return False

        print(f"[{self._log_tag}] 检测到 Barotem 登录失效"
              f"（{reason}），当前页面={self.page.url}")
        result = await self._session.relogin(self.page)
        if result.get("status") != "success":
            self._relogin_failures += 1
            message = result.get("message", "未知原因")
            if self._relogin_failures >= RELOGIN_MAX_ATTEMPTS:
                self._relogin_disabled = True
                print(f"[{self._log_tag}] Barotem 自动重新登录连续失败 "
                      f"{self._relogin_failures} 次，已暂停: {message}")
                await play_alert_audio_async(
                    text=(f"barotem账号{self._session.account_id}"
                          "连续登录失败，已暂停自动登录，请检查凭证")
                )
                return False

            backoff_index = min(
                self._relogin_failures - 1,
                len(RELOGIN_BACKOFF_SECONDS) - 1,
            )
            backoff_seconds = RELOGIN_BACKOFF_SECONDS[backoff_index]
            self._next_relogin_at = time.monotonic() + backoff_seconds
            self._last_relogin_wait_log_at = 0.0
            print(f"[{self._log_tag}] Barotem 自动重新登录失败"
                  f"（第 {self._relogin_failures}/{RELOGIN_MAX_ATTEMPTS} 次）: "
                  f"{message}；{int(backoff_seconds)} 秒后再试")
            return False

        self._relogin_failures = 0
        self._next_relogin_at = 0.0
        self._relogin_disabled = False
        ready = await self._goto_business_page(
            target_url, ready_selector, wait_timeout,
            reason="重新登录后返回业务页",
        )
        if not ready:
            raise RuntimeError(
                "Barotem 重新登录成功，但业务页仍要求登录")
        await self._stop_relogin_alerts()
        print(f"[{self._log_tag}] Barotem 自动重新登录并恢复业务页成功")
        return True

    async def _wait_business_area(
            self, selector: str, wait_timeout: int) -> bool:
        ready_timeout = max(wait_timeout, MIN_READY_TIMEOUT_MS)
        try:
            await self._handle_page_popups()
            await self.page.wait_for_selector(
                selector,
                state="attached",
                timeout=ready_timeout,
            )
            await self._handle_page_popups()
            return True
        except Exception as exc:
            print(f"[{self._log_tag}] 等待业务区域超时"
                  f"（{ready_timeout}ms, selector={selector}）: {exc}")
            return False

    async def _goto_business_page(
            self, url: str, ready_selector: str,
            wait_timeout: int, reason: str):
        print(f"[{self._log_tag}] [页面导航] {reason}: {url}")
        previous_origin = await _read_document_time_origin(self.page)
        committed = False
        try:
            await self.page.goto(
                url,
                wait_until="commit",
                timeout=max(wait_timeout, MIN_COMMIT_TIMEOUT_MS),
            )
            committed = True
        except Exception as exc:
            if self.page.is_closed():
                raise
            print(f"[{self._log_tag}] [页面导航] 提交阶段异常: {exc}；"
                  "短暂复核新文档是否已经提交")
            committed = await _wait_for_document_change(
                self.page, previous_origin)

        if committed and await self._login_required():
            return False
        if committed and await self._wait_business_area(
                ready_selector, wait_timeout):
            return True
        raise RuntimeError(f"Barotem 页面导航后关键区域未就绪: {url}")

    async def _reload_business_page(
            self, target_url: str, ready_selector: str,
            wait_timeout: int, reason: str):
        previous_origin = await _read_document_time_origin(self.page)
        committed = False
        navigation_error = None
        try:
            await self.page.reload(
                wait_until="commit",
                timeout=max(wait_timeout, MIN_COMMIT_TIMEOUT_MS),
            )
            committed = True
        except Exception as exc:
            if self.page.is_closed():
                raise
            navigation_error = exc
            print(f"[{self._log_tag}] [{reason}] reload 提交阶段异常: "
                  f"{exc}；复核新文档是否已经提交")
            committed = await _wait_for_document_change(
                self.page, previous_origin)

        if committed and await self._login_required():
            return False
        if committed and await self._wait_business_area(
                ready_selector, wait_timeout):
            return True

        print(f"[{self._log_tag}] [{reason}] 无法确认最新页面，执行一次受控导航")
        try:
            return await self._goto_business_page(
                target_url, ready_selector, wait_timeout,
                reason=f"{reason}-受控恢复",
            )
        except Exception as exc:
            if navigation_error is not None:
                raise RuntimeError(
                    f"Barotem {reason}和受控恢复均失败"
                ) from navigation_error
            raise exc


class BarotemOrderWorker(_BarotemWorker):
    """订单 Worker：固定在 판매중 页面，定时刷新并提取订单。"""

    def __init__(self, session, stop_event, monitor: 'BarotemMonitor'):
        super().__init__(
            session, stop_event, monitor, name="BarotemOrder")

    async def run(self):
        cfg = self._monitor.get_order_cfg()
        refresh_interval = cfg.get("refresh_interval", 3)
        wait_timeout = cfg.get("wait_timeout", 10000)
        print(f"[{self._log_tag}] 订单监控循环开始 "
              f"(interval={refresh_interval}s)")
        check_round = 0

        while not self.stopped:
            check_round += 1
            self._touch()
            if self._page_crashed:
                raise RuntimeError("订单页渲染进程已崩溃")
            if not await self._ensure_order_page_ready(wait_timeout):
                await asyncio.sleep(refresh_interval)
                continue
            try:
                reported = await self._collect_all_order_categories(
                    wait_timeout)
                if reported:
                    print(f"[{self._log_tag}] 第{check_round}轮: "
                          f"上报 {reported} 个订单")
            except Exception as exc:
                print(f"[{self._log_tag}] 第{check_round}轮异常: {exc}")

            await self._reload_order_page(wait_timeout)
            await asyncio.sleep(refresh_interval)

    async def _collect_all_order_categories(
            self, wait_timeout: int) -> int:
        """按页面计数依次采集所有非空分类，避免只监控默认“账号”分类。"""
        available_types = await self._available_order_types()
        if not available_types:
            return await self._monitor._collect_and_report_orders(self.page)

        reported = 0
        for item_type in available_types:
            query = parse_qs(urlparse(self.page.url).query)
            current_type = query.get("itemtype", [""])[0]
            current_limit = query.get("limit", [""])[0]
            if current_type != item_type or current_limit != "500":
                ready = await self._goto_business_page(
                    _order_list_url(item_type),
                    ORDER_CONTENT_SELECTOR,
                    wait_timeout,
                    reason=f"采集订单分类-{item_type}",
                )
                recovery = await self._recover_login_if_needed(
                    _order_list_url(item_type),
                    ORDER_CONTENT_SELECTOR,
                    wait_timeout,
                    reason=f"进入订单分类-{item_type}",
                )
                if recovery is False:
                    break
                if recovery is None and not ready:
                    raise RuntimeError(
                        f"订单分类 {item_type} 导航后仍要求登录")
            reported += await self._monitor._collect_and_report_orders(
                self.page)
        return reported

    async def _available_order_types(self) -> List[str]:
        values = await self.page.locator("[data-item]").evaluate_all("""
            elements => elements.map(element => ({
                itemType: element.getAttribute('data-item') || '',
                text: (element.innerText || '').trim()
            }))
        """)
        available = []
        for value in values:
            item_type = _compact_text(value.get("itemType"))
            count_match = re.findall(r"\d+", str(value.get("text") or ""))
            count = int(count_match[-1]) if count_match else 0
            if item_type in PRODUCT_TYPES and count > 0:
                available.append(item_type)
        return available

    async def _ensure_order_page_ready(self, wait_timeout: int) -> bool:
        recovery = await self._recover_login_if_needed(
            ORDER_LIST_URL, ORDER_CONTENT_SELECTOR,
            wait_timeout, reason="订单检测前",
        )
        if recovery is not None:
            return recovery

        if "/mypage/sellview/4" not in self.page.url:
            ready = await self._goto_business_page(
                ORDER_LIST_URL, ORDER_CONTENT_SELECTOR,
                wait_timeout, reason="初始化订单页",
            )
            recovery = await self._recover_login_if_needed(
                ORDER_LIST_URL, ORDER_CONTENT_SELECTOR,
                wait_timeout, reason="进入订单页时",
            )
            if recovery is not None:
                return recovery
            if not ready:
                raise RuntimeError("订单页导航后仍要求登录")

        if await self._wait_business_area(
                ORDER_CONTENT_SELECTOR, wait_timeout):
            return True
        ready = await self._goto_business_page(
            ORDER_LIST_URL, ORDER_CONTENT_SELECTOR,
            wait_timeout, reason="恢复订单页",
        )
        if ready:
            return True
        recovery = await self._recover_login_if_needed(
            ORDER_LIST_URL, ORDER_CONTENT_SELECTOR,
            wait_timeout, reason="恢复订单页时",
        )
        return bool(recovery)

    async def _reload_order_page(self, wait_timeout: int):
        recovery = await self._recover_login_if_needed(
            ORDER_LIST_URL, ORDER_CONTENT_SELECTOR,
            wait_timeout, reason="刷新订单页前",
        )
        if recovery is not None:
            return
        ready = await self._reload_business_page(
            ORDER_LIST_URL, ORDER_CONTENT_SELECTOR,
            wait_timeout, reason="订单页刷新",
        )
        recovery = await self._recover_login_if_needed(
            ORDER_LIST_URL, ORDER_CONTENT_SELECTOR,
            wait_timeout, reason="刷新订单页后",
        )
        if recovery is None and not ready:
            raise RuntimeError("订单页刷新后仍要求登录")


class BarotemRefreshWorker(_BarotemWorker):
    """商品刷新 Worker：轮换有商品的分类并点击「끌어올리기」。"""

    def __init__(self, session, stop_event, monitor: 'BarotemMonitor'):
        super().__init__(
            session, stop_event, monitor, name="BarotemRefresh")
        self._last_refresh = datetime.datetime.now()
        self._product_type_index = 0

    async def run(self):
        wait_timeout = self._monitor.get_order_cfg().get(
            "wait_timeout", 10000)
        interval = 40
        await self._ensure_refresh_page_ready(wait_timeout)
        try:
            await self._sync_sales_products(wait_timeout)
        except Exception as exc:
            print(f"[{self._log_tag}] 初始销售商品快照同步失败: {exc}")
            if self.page_failure_requires_rebuild(exc):
                raise
        if SCHEDULED_PRODUCT_REFRESH_ENABLED:
            print(f"[{self._log_tag}] 商品顶帖就绪 (间隔={interval}s)")
        else:
            print(f"[{self._log_tag}] Barotem 定时顶帖已关闭，"
                  f"仅同步在售商品快照 (间隔={interval}s)")
        actions_on_page = 0

        while not self.stopped:
            self._touch()
            if self._page_crashed:
                raise RuntimeError("上架页渲染进程已崩溃")
            elapsed = (
                datetime.datetime.now() - self._last_refresh
            ).total_seconds()
            if elapsed >= interval:
                try:
                    result = await self._run_refresh_cycle(wait_timeout)
                    self._last_refresh = datetime.datetime.now()
                    if result == "refreshed":
                        actions_on_page += 1
                    if actions_on_page >= REFRESH_PAGE_MAX_ACTIONS:
                        await self.recycle_page(
                            f"上架页已执行 {actions_on_page} 次顶帖，"
                            "主动释放页面内存",
                        )
                        await self._ensure_refresh_page_ready(wait_timeout)
                        actions_on_page = 0
                except Exception as exc:
                    print(f"[{self._log_tag}] 商品顶帖或快照同步异常: {exc}")
                    if self.page_failure_requires_rebuild(exc):
                        raise RuntimeError(
                            "上架页已不可用，需要重建标签"
                        ) from exc
            await asyncio.sleep(5)

    async def _run_refresh_cycle(self, timeout: int) -> str:
        if not SCHEDULED_PRODUCT_REFRESH_ENABLED:
            await self._prepare_refresh_action_page(timeout)
            await self._sync_sales_products(timeout)
            return "scheduled_refresh_disabled"

        result = await self._do_refresh(timeout)
        await self._sync_sales_products(timeout)
        return result

    async def _do_refresh(self, timeout: int) -> str:
        await self._prepare_refresh_action_page(timeout)
        available_types = await self._available_product_types()
        if not available_types:
            print(f"[{self._log_tag}] 当前没有可顶帖的上架商品")
            return "nothing_to_refresh"

        item_type = available_types[
            self._product_type_index % len(available_types)]
        self._product_type_index += 1
        target_url = _product_list_url(item_type)
        query = parse_qs(urlparse(self.page.url).query)
        current_type = query.get("itemtype", [""])[0]
        current_limit = query.get("limit", [""])[0]
        if current_type != item_type or current_limit != "500":
            ready = await self._goto_business_page(
                target_url, REFRESH_CONTENT_SELECTOR, timeout,
                reason=f"切换商品分类-{item_type}",
            )
            if not ready:
                recovery = await self._recover_login_if_needed(
                    target_url, REFRESH_CONTENT_SELECTOR,
                    timeout, reason=f"切换商品分类-{item_type}",
                )
                if not recovery:
                    raise RuntimeError("切换商品分类时登录恢复失败")

        cards = self.page.locator(REFRESH_CARD_SELECTOR)
        card_count = await cards.count()
        if card_count == 0:
            print(f"[{self._log_tag}] 分类 {item_type} 当前无上架商品")
            return "nothing_to_refresh"

        target_card = cards.nth(card_count - 1)
        button = target_card.locator(REFRESH_BUTTON_SELECTOR).first
        if await button.count() == 0:
            print(f"[{self._log_tag}] 最旧商品没有 끌어올리기 按钮")
            return "nothing_to_refresh"
        onclick = await button.get_attribute("onclick") or ""
        product_id = _parse_refresh_product_id(onclick)
        if not product_id:
            raise RuntimeError("顶帖按钮缺少有效商品编号")

        print(f"[{self._log_tag}] 顶帖商品: "
              f"type={item_type}, product_id={product_id}")
        await button.click(timeout=max(timeout, MIN_COMMIT_TIMEOUT_MS))
        confirm = self.page.locator(
            f"{REFRESH_CONFIRM_SELECTOR}:visible").last
        await confirm.wait_for(
            state="visible",
            timeout=max(timeout, MIN_COMMIT_TIMEOUT_MS),
        )
        await confirm.click(timeout=max(timeout, MIN_COMMIT_TIMEOUT_MS))
        return await self._wait_refresh_result(product_id, timeout)

    async def _wait_refresh_result(
            self, product_id: str, timeout: int) -> str:
        deadline = time.monotonic() + max(
            REFRESH_RESULT_TIMEOUT_SECONDS,
            max(timeout, MIN_COMMIT_TIMEOUT_MS) / 1000,
        )
        success_confirm_clicked = False
        while time.monotonic() < deadline:
            if await self._login_required():
                raise RuntimeError("商品顶帖后登录失效")

            confirm = self.page.locator(
                f"{REFRESH_CONFIRM_SELECTOR}:visible").last
            if not success_confirm_clicked and await confirm.count() > 0:
                try:
                    title = self.page.locator(
                        "#commonAlert .common_alert_wrap h2").last
                    title_text = (
                        await title.inner_text()
                        if await title.count() > 0 else ""
                    )
                    # 首个弹窗是“是否顶帖”的确认。只有 AJAX 返回的第二个
                    # 结果弹窗才能再次点击，避免网络较慢时重复提交。
                    is_result_dialog = (
                        "해당 물품에 끌어올리기를" not in title_text
                    )
                    if is_result_dialog and await confirm.is_visible():
                        await confirm.click(timeout=2000)
                        success_confirm_clicked = True
                except Exception:
                    pass

            card = self.page.locator(
                f'#product_title_input_{product_id}')
            if success_confirm_clicked and await card.count() > 0:
                print(f"[{self._log_tag}] 商品顶帖提交成功: {product_id}")
                return "refreshed"
            if self.page.is_closed():
                raise RuntimeError("商品顶帖结果检查时页面已关闭")
            await asyncio.sleep(0.25)

        raise RuntimeError(
            f"商品顶帖后未确认到有效结果: product_id={product_id}")

    async def _available_product_types(self) -> List[str]:
        counts = await self._product_category_counts()
        return [
            item_type for item_type in PRODUCT_TYPES
            if counts[item_type] > 0
        ]

    async def _product_category_counts(self) -> dict:
        values = await self.page.locator("[data-item]").evaluate_all("""
            elements => elements.map(element => ({
                itemType: element.getAttribute('data-item') || '',
                text: (element.innerText || '').trim()
            }))
        """)
        counts = {}
        for value in values:
            item_type = _compact_text(value.get("itemType"))
            count_match = re.findall(r"\d+", str(value.get("text") or ""))
            count = int(count_match[-1]) if count_match else 0
            if item_type in PRODUCT_TYPES:
                counts[item_type] = count
        missing = [value for value in PRODUCT_TYPES if value not in counts]
        if missing:
            raise RuntimeError(
                f"商品分类计数不完整，停止快照同步: {missing}")
        return counts

    async def _sync_sales_products(self, timeout: int) -> dict:
        first = await self._collect_sales_products_snapshot(timeout)
        second = await self._collect_sales_products_snapshot(timeout)
        first_by_id = {
            product["platform_product_id"]: product
            for product in first
        }
        second_by_id = {
            product["platform_product_id"]: product
            for product in second
        }
        if first_by_id != second_by_id:
            raise RuntimeError(
                "Barotem 两次商品列表快照不一致，"
                "停止同步以避免误删")
        products = list(second_by_id.values())
        result = await asyncio.to_thread(
            self._monitor.reporter.sync_sales_products_snapshot,
            self._monitor.account_id,
            "barotem",
            products,
        )
        if not result.get("success"):
            raise RuntimeError(
                result.get("error") or "总控未确认销售商品快照")
        print(
            f"[{self._log_tag}] 销售商品快照已同步: "
            f"total={result.get('received_count', len(products))}, "
            f"inserted={result.get('inserted_count', 0)}, "
            f"updated={result.get('updated_count', 0)}, "
            f"unchanged={result.get('unchanged_count', 0)}, "
            f"deleted={result.get('deleted_count', 0)}"
        )
        return result

    async def _collect_sales_products_snapshot(
            self, timeout: int) -> List[dict]:
        """
        抓取所有分类和分页。只有数量与页面计数完全一致时才返回，
        从而保证后端可以安全物理删除本轮缺失的商品。
        """
        await self._prepare_refresh_action_page(timeout)
        counts = await self._product_category_counts()
        products = []
        seen_product_ids = set()
        scanned_total = 0

        for item_type in PRODUCT_TYPES:
            total = counts[item_type]
            if total == 0:
                continue
            page_count = (total + PRODUCT_PAGE_SIZE - 1) // PRODUCT_PAGE_SIZE
            collected_for_type = 0

            for page_number in range(1, page_count + 1):
                target_url = _product_list_url(item_type, page_number)
                query = parse_qs(urlparse(self.page.url).query)
                current_type = query.get("itemtype", [""])[0]
                current_page = query.get("page", [""])[0]
                current_limit = query.get("limit", [""])[0]
                if (
                    current_type != item_type
                    or current_page != str(page_number)
                    or current_limit != str(PRODUCT_PAGE_SIZE)
                ):
                    ready = await self._goto_business_page(
                        target_url,
                        REFRESH_CONTENT_SELECTOR,
                        timeout,
                        reason=(
                            f"抓取销售商品-{item_type}-"
                            f"第{page_number}页"
                        ),
                    )
                    if not ready:
                        recovery = await self._recover_login_if_needed(
                            target_url,
                            REFRESH_CONTENT_SELECTOR,
                            timeout,
                            reason=(
                                f"抓取销售商品-{item_type}-"
                                f"第{page_number}页"
                            ),
                        )
                        if not recovery:
                            raise RuntimeError(
                                "抓取销售商品时登录恢复失败")

                page_snapshot = await self._extract_sales_products_page(
                    item_type)
                page_products = page_snapshot["products"]
                expected = min(
                    PRODUCT_PAGE_SIZE,
                    total - collected_for_type,
                )
                if page_snapshot["total_cards"] != expected:
                    raise RuntimeError(
                        f"商品分类 {item_type} 第 {page_number} 页"
                        f"数量不一致: expected={expected}, "
                        f"actual={page_snapshot['total_cards']}；"
                        "停止完整快照同步以避免误删"
                    )
                for product in page_products:
                    product_id = product["platform_product_id"]
                    if product_id in seen_product_ids:
                        raise RuntimeError(
                            f"完整快照出现重复商品 ID: {product_id}")
                    seen_product_ids.add(product_id)
                    products.append(product)
                collected_for_type += page_snapshot["total_cards"]
                scanned_total += page_snapshot["total_cards"]

            if collected_for_type != total:
                raise RuntimeError(
                    f"商品分类 {item_type} 抓取不完整: "
                    f"expected={total}, actual={collected_for_type}")

        expected_total = sum(counts.values())
        if scanned_total != expected_total:
            raise RuntimeError(
                f"销售商品完整快照数量不一致: "
                f"expected={expected_total}, actual={scanned_total}")
        return products

    async def _extract_sales_products_page(
            self, item_type: str) -> dict:
        snapshot = await self.page.locator(
            REFRESH_CARD_SELECTOR).evaluate_all("""
            cards => ({
              total_cards: cards.length,
              products: cards
                .filter(card => !card.classList.contains('on'))
                .map(card => {
                const heading = card.querySelector(
                    '.product_detail_info h4'
                );
                const game = heading
                    ? heading.querySelector('span')
                    : null;
                const region = heading
                    ? Array.from(heading.childNodes)
                        .filter(node => node.nodeType === 3)
                        .map(node => node.textContent || '')
                        .join(' ')
                    : '';
                const priceGroups = Array.from(
                    card.querySelectorAll(
                        '.product_detail_price > div'
                    )
                );
                const groupValue = group => {
                    if (!group) return '';
                    const values = Array.from(
                        group.querySelectorAll('h4')
                    );
                    return values.length
                        ? (values[values.length - 1].innerText || '')
                        : '';
                };
                const checkbox = card.querySelector(
                    'input.product_checkbox'
                );
                return {
                    platform_product_id: checkbox
                        ? (checkbox.value || '')
                        : '',
                    game_name: game
                        ? (game.innerText || '')
                        : '',
                    region_name: region,
                    title: (
                        card.querySelector(
                            '.product_detail_info p'
                        )?.innerText || ''
                    ),
                    quantity_text: groupValue(priceGroups[0]),
                    price_text: groupValue(priceGroups[1]),
                    platform_registered_at: (
                        card.querySelector(
                            '.product_title time'
                        )?.innerText || ''
                    )
                  };
                })
            })
        """)
        return {
            "total_cards": snapshot.get("total_cards", 0),
            "products": [
                _parse_sales_product_card_payload(payload, item_type)
                for payload in snapshot.get("products", [])
            ],
        }

    async def _prepare_refresh_action_page(self, timeout: int):
        recovery = await self._recover_login_if_needed(
            SELL_LIST_URL, REFRESH_CONTENT_SELECTOR,
            timeout, reason="刷新上架页前",
        )
        if recovery is not None:
            if not recovery:
                raise RuntimeError("Barotem 登录恢复正在退避")
            return

        if SELL_LIST_URL not in self.page.url:
            ready = await self._goto_business_page(
                _product_list_url("money"),
                REFRESH_CONTENT_SELECTOR, timeout,
                reason="恢复上架页",
            )
            if not ready:
                recovery = await self._recover_login_if_needed(
                    _product_list_url("money"),
                    REFRESH_CONTENT_SELECTOR,
                    timeout, reason="恢复上架页",
                )
                if not recovery:
                    raise RuntimeError("恢复上架页时登录恢复失败")
            return

        target_url = self.page.url
        ready = await self._reload_business_page(
            target_url, REFRESH_CONTENT_SELECTOR,
            timeout, reason="上架页刷新",
        )
        if not ready:
            recovery = await self._recover_login_if_needed(
                target_url, REFRESH_CONTENT_SELECTOR,
                timeout, reason="刷新上架页后",
            )
            if not recovery:
                raise RuntimeError("刷新上架页时登录恢复失败")

    async def _ensure_refresh_page_ready(self, timeout: int):
        if (
            SELL_LIST_URL in self.page.url
            and await self._wait_business_area(
                REFRESH_CONTENT_SELECTOR, timeout)
        ):
            return
        ready = await self._goto_business_page(
            _product_list_url("money"),
            REFRESH_CONTENT_SELECTOR, timeout,
            reason="初始化上架页",
        )
        if not ready:
            recovery = await self._recover_login_if_needed(
                _product_list_url("money"),
                REFRESH_CONTENT_SELECTOR,
                timeout, reason="初始化上架页",
            )
            if not recovery:
                raise RuntimeError("初始化上架页时登录恢复失败")


class BarotemMonitor(BaseOrderMonitor):
    """Barotem 站点订单监控。"""

    tag = "barotem"

    def get_order_cfg(self) -> dict:
        return {
            "my_page_url": ORDER_LIST_URL,
            "my_page_selector": ORDER_CONTENT_SELECTOR,
            "wait_timeout": 10000,
            "refresh_interval": 3,
            "max_retries": 999,
        }

    def _get_workers(self) -> List[PageWorker]:
        if not self._session:
            raise RuntimeError("BrowserSession 未初始化")
        return [
            BarotemOrderWorker(
                self._session, self.stop_event, self),
            BarotemRefreshWorker(
                self._session, self.stop_event, self),
        ]

    def _is_target_page(self, url: str) -> bool:
        return (
            SELL_LIST_URL in url
            or "/mypage/sellview/" in url
        )

    def _is_on_collect_page(self, page) -> bool:
        return "/mypage/sellview/4" in page.url

    async def _get_product_detail(self, page, product_id: str) -> dict:
        cache = getattr(self, "_product_detail_cache", None)
        if cache is None:
            cache = {}
            self._product_detail_cache = cache
        cached = cache.get(product_id)
        if cached:
            return dict(cached)
        detail = await _fetch_product_detail(page, product_id)
        cache[product_id] = dict(detail)
        return detail

    async def _extract_orders_from_table(
            self, page) -> OrderExtractionResult:
        content = page.locator(ORDER_CONTENT_SELECTOR).first
        if await content.count() == 0:
            return OrderExtractionResult.failure(
                f"未找到 {ORDER_CONTENT_SELECTOR} 订单区域")

        cards = page.locator(ORDER_CARD_SELECTOR)
        card_count = await cards.count()
        if card_count == 0:
            if await content.locator(".product_empty").count() > 0:
                return OrderExtractionResult.success([])
            return OrderExtractionResult.failure(
                "订单区域存在，但未找到订单卡片或空列表标记")

        query = parse_qs(urlparse(page.url).query)
        mode_match = re.search(r"/mypage/sellview/(\d+)", page.url)
        mode = mode_match.group(1) if mode_match else ""
        item_type = query.get("itemtype", ["unknown"])[0]
        orders = []
        failed_rows = 0
        seen_order_ids = set()

        for index in range(card_count):
            try:
                payload = await cards.nth(index).evaluate("""
                    card => {
                        const heading = card.querySelector(
                            '.product_detail_info h4'
                        );
                        const game = heading
                            ? heading.querySelector('span')
                            : null;
                        const server = heading
                            ? Array.from(heading.childNodes)
                                .filter(node => node.nodeType === 3)
                                .map(node => node.textContent || '')
                                .join(' ')
                            : '';
                        const priceGroups = Array.from(
                            card.querySelectorAll(
                                '.product_detail_price > div'
                            )
                        );
                        const groupValue = group => {
                            if (!group) return '';
                            const values = Array.from(
                                group.querySelectorAll('h4')
                            );
                            return values.length
                                ? (values[values.length - 1].innerText || '')
                                : '';
                        };
                        const checkbox = card.querySelector(
                            'input.product_checkbox'
                        );
                        const buyer = card.querySelector(
                            '[onclick^="dealinfo("]'
                        );
                        const product = card.querySelector(
                            '.product_detail_info[onclick*="productview("]'
                        );
                        const chat = card.querySelector(
                            '[onclick*="/chat/view?jangNum="]'
                        );
                        return {
                            order_no: checkbox
                                ? (checkbox.value || '')
                                : '',
                            game_name: game
                                ? (game.innerText || '')
                                : '',
                            server,
                            title: (
                                card.querySelector(
                                    '.product_detail_info p'
                                )?.innerText || ''
                            ),
                            amount: groupValue(priceGroups[0]),
                            price: groupValue(priceGroups[1]),
                            buyer_onclick: buyer
                                ? (buyer.getAttribute('onclick') || '')
                                : '',
                            product_onclick: product
                                ? (product.getAttribute('onclick') || '')
                                : '',
                            chat_onclick: chat
                                ? (chat.getAttribute('onclick') || '')
                                : '',
                            order_time: (
                                card.querySelector(
                                    '.product_title time'
                                )?.innerText || ''
                            ),
                            status: (
                                card.querySelector(
                                    '.product_title h4'
                                )?.className || ''
                            )
                        };
                    }
                """)
                payload["mode"] = mode
                payload["item_type"] = item_type
                product_id = _parse_product_view_id(
                    payload.get("product_onclick", ""))
                payload["platform_product_id"] = product_id
                chat_url = _parse_chat_view_url(
                    payload.get("chat_onclick", ""))
                cache_chat_url = getattr(
                    self._session, "remember_conversation_url", None)
                if chat_url and callable(cache_chat_url):
                    cache_chat_url(
                        "barotem", payload.get("order_no", ""), chat_url)
                if product_id:
                    try:
                        payload.update(await self._get_product_detail(
                            page, product_id))
                    except Exception as exc:
                        print(f"[{self._log_tag}] 订单卡片 #{index} "
                              f"商品详情读取失败 product_id={product_id}: "
                              f"{exc}")
                parsed = _parse_order_card_payload(payload)
                if parsed and parsed["order_no"] not in seen_order_ids:
                    orders.append(parsed)
                    seen_order_ids.add(parsed["order_no"])
            except Exception as exc:
                failed_rows += 1
                print(f"[{self._log_tag}] 订单卡片 #{index} "
                      f"提取失败: {exc}")

        if card_count > 0 and failed_rows == card_count:
            return OrderExtractionResult.failure(
                f"订单区域有 {card_count} 张卡片，但全部解析失败")
        return OrderExtractionResult.success(orders)

    async def _build_normalized_order(
            self, page, order_data: dict):
        del page
        if not order_data.get("buyer_character"):
            print(f"[{self._log_tag}] 订单 "
                  f"{order_data.get('order_no', '?')} "
                  "未提取到买家角色名，停止上报")
            return None

        try:
            quantity_value = _resolve_order_quantity(
                order_data.get("amount", ""),
                detail_price=order_data.get("detail_price", ""),
                minimum_quantity=order_data.get("minimum_quantity", ""),
                require_detail=order_data.get("item_type") == "money",
            )
        except ValueError as exc:
            print(f"[{self._log_tag}] 订单 "
                  f"{order_data.get('order_no', '?')} "
                  f"数量解析失败: {exc}")
            return None

        try:
            platform_price = parse_korean_amount(
                order_data.get("price", "").replace("원", ""))
        except ValueError:
            platform_price = Decimal("0")

        adapter = adapter_for("barotem")
        normalized_data = dict(order_data)
        normalized_data["amount"] = format(quantity_value, "f")
        normalized = adapter.normalize(
            normalized_data,
            platform_order_time=order_data.get(
                "platform_order_time", ""),
            platform_price=platform_price,
            platform_item_type=order_data.get("item_type", ""),
            product_title=order_data.get("item_name", ""),
            quantity=int(quantity_value),
            sale_quantity=int(quantity_value),
        )
        if normalized is None:
            print(f"[{self._log_tag}] 适配器拒绝订单 "
                  f"{order_data.get('order_no', '?')}: "
                  f"{adapter.last_reject_reason}")
        return normalized

    async def post_login_check(self, page) -> bool:
        """只检测当前可见的登录提示，忽略通用弹窗残留回调。"""
        try:
            checks = page.locator(LOGIN_ALERT_SELECTOR)
            for index in range(await checks.count()):
                check = checks.nth(index)
                onclick = await check.get_attribute("onclick") or ""
                if "/auth/login" in onclick:
                    print(f"[{self._log_tag}] 检测到登录弹窗，需要重新登录")
                    return True
        except Exception:
            pass
        return False
