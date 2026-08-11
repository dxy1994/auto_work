"""
ItemBay 订单监控（Async 多页面并行架构）。

Worker 分工：
  - ItembayOrderWorker：固定在销售进行页，刷新、提取并上报订单
  - ItembayRefreshWorker：从上架列表进入修改页，定时保存商品

ItemBay 的销售进行页在站点主页面中由 iframe 承载。Worker 直接打开
iframe 的 SSL 地址，让订单表格成为顶层文档，避免父页面和 iframe
分别刷新造成状态判断不稳定。
"""
import asyncio
import datetime
import html
import re
import time
from decimal import Decimal
from typing import List, Optional
from urllib.parse import urljoin

from monitor.browser.audio import play_alert_audio_async
from monitor.monitoring.base import BaseOrderMonitor
from monitor.monitoring.extraction import OrderExtractionResult
from monitor.monitoring.worker import PageWorker
from monitor.orders.adapters import adapter_for, parse_korean_amount


SELL_LIST_URL = (
    "https://www.itembay.com/mybay/status/mybayStatusSellList"
)
ORDER_LIST_URL = (
    "https://www.itembay.com/mybay/status/mybayStatusGiveListBySSL"
)
BAYTALK_LIST_URL = (
    "https://www.itembay.com/ibmessenger/bayTalkListMain"
)

ORDER_TABLE_SELECTOR = "table.list_type"
ORDER_ROW_SELECTOR = "table.list_type tbody tr"
REFRESH_TABLE_SELECTOR = "#frmMybay .list_type"
REFRESH_ROW_SELECTOR = "#frmMybay .list_type tbody tr"
EDIT_BUTTON_SELECTOR = 'a[title="수정"]'
EDIT_SUBMIT_SELECTOR = "#imgSubmitButton"
EDIT_PAGE_PATHS = (
    "/item/sell/sellEdit",
    "/item/sell/sellDivisionEdit",
)
LAST_PAGE_SELECTOR = (
    '#NavigationPanel a:has(img[alt="마지막 페이지"])'
)
NEXT_PAGE_SELECTOR = (
    '#NavigationPanel a:has(img[alt="다음 페이지"])'
)
PRESALE_LIST_SELECTOR = "#before_chat_list"
PRESALE_ROW_SELECTOR = "#before_chat_list .item_list"
PRESALE_TAB_SELECTOR = '.btn_tab[data-type="before"]'

MIN_COMMIT_TIMEOUT_MS = 15000
MIN_READY_TIMEOUT_MS = 20000
COMMIT_GRACE_SECONDS = 3.0
REFRESH_RESULT_TIMEOUT_SECONDS = 15.0
REFRESH_PAGE_MAX_ACTIONS = 30
RELOGIN_MAX_ATTEMPTS = 3
RELOGIN_BACKOFF_SECONDS = (30.0, 120.0)
MAX_SALES_PRODUCT_PAGES = 1000
PRESALE_POLL_INTERVAL_SECONDS = 5.0
PRESALE_LIST_REFRESH_INTERVAL_SECONDS = 15.0
PRESALE_ALERT_INTERVAL_SECONDS = 20.0


def _compact_text(value) -> str:
    return " ".join(str(value or "").split())


def _parse_presale_inquiry_payload(payload: dict) -> Optional[dict]:
    """Normalize one live BayTalk pre-sale row when it has unread messages."""
    unread_text = _compact_text(payload.get("unread_text"))
    match = re.search(r"\d[\d,]*", unread_text)
    if not match:
        return None
    unread_count = int(match.group(0).replace(",", ""))
    if unread_count <= 0:
        return None
    return {
        "talk_seq": _compact_text(payload.get("talk_seq")),
        "item_seq": _compact_text(payload.get("item_seq")),
        "game_server": _compact_text(payload.get("game_server")),
        "last_time": _compact_text(payload.get("last_time")),
        "unread_count": unread_count,
    }


def _parse_sales_product_row_payload(payload: dict) -> dict:
    product_id = _compact_text(payload.get("platform_product_id"))
    if not re.fullmatch(r"\d+", product_id):
        raise ValueError("未提取到有效的 ItemBay 商品 ID")

    game_region = _compact_text(payload.get("game_region"))
    game_name = ""
    region_name = ""
    if " - " in game_region:
        game_name, region_name = game_region.rsplit(" - ", 1)
    return {
        "platform_product_id": product_id,
        "platform_item_type": _compact_text(
            payload.get("platform_item_type")),
        "game_name": _compact_text(game_name),
        "region_name": _compact_text(region_name),
        "title": _compact_text(payload.get("title")),
        "quantity_text": _compact_text(payload.get("quantity_text")),
        "price_text": _compact_text(payload.get("price_text")),
        "platform_registered_at": _compact_text(
            payload.get("platform_registered_at")),
    }


def _parse_edit_action(onclick: str) -> Optional[dict]:
    """解析 fncSellEdit(itemSeq, sellStatus, divisionFlag)。"""
    match = re.search(
        r"fncSellEdit\s*\((?P<args>[^)]*)\)",
        str(onclick or ""),
    )
    if not match:
        return None
    args = [
        part.strip().strip("'\"")
        for part in match.group("args").split(",")
    ]
    if len(args) < 3 or not re.fullmatch(r"\d+", args[0]):
        return None
    try:
        return {
            "item_seq": args[0],
            "sell_status": int(args[1] or "0"),
            "division": args[2] == "1",
        }
    except ValueError:
        return None


def _extract_transaction_id(attributes: List[str]) -> str:
    source = " ".join(str(value or "") for value in attributes)
    patterns = (
        r"[?&]iTranSeq=(\d+)",
        r"fncSetGiveItem\s*\(\s*['\"]?(\d+)",
        r"fncCancel\s*\(\s*['\"]?(\d+)",
        r"\biTranSeq\s*[:=]\s*['\"]?(\d+)",
    )
    for pattern in patterns:
        match = re.search(pattern, source, re.IGNORECASE)
        if match:
            return match.group(1)
    return ""


def _extract_character_name(candidates: List[dict],
                            progress_text: str) -> str:
    for candidate in candidates or []:
        copy_action = " ".join((
            str(candidate.get("onclick") or ""),
            str(candidate.get("href") or ""),
        ))
        match = re.search(
            r"fncCharacterNameCopy\s*\(\s*(['\"])(.*?)\1",
            copy_action,
        )
        if match:
            value = html.unescape(match.group(2))
            value = value.replace("#quot#", '"').replace("#apos#", "'")
            if _compact_text(value):
                return _compact_text(value)

        for key in ("data_character_name", "data_character"):
            value = _compact_text(candidate.get(key))
            if value:
                return value

        value = _compact_text(candidate.get("text"))
        if value and value not in {"복사", "캐릭터명 복사", "닉네임 복사"}:
            return value

    progress = str(progress_text or "")
    match = re.search(
        r"(?:캐릭터(?:명)?|닉네임)\s*[:：]?\s*([^\n\r|]+)",
        progress,
    )
    return _compact_text(match.group(1)) if match else ""


def _combine_order_row_payloads(payloads: List[dict]) -> List[dict]:
    """Combine ItemBay's primary row with its buyer-information row.

    Live orders use ``rowspan=2`` on the item-number cell.  The first row
    contains the product and transaction data, while the following row holds
    the buyer character and BayTalk action.  Treating both rows as standalone
    records loses the character name and turns the buyer row into a parse
    error.
    """
    combined = []
    index = 0
    while index < len(payloads or []):
        payload = dict(payloads[index] or {})
        cells = list(payload.get("cells") or [])

        if payload.get("is_buyer_detail"):
            index += 1
            continue

        try:
            row_span = max(1, int(payload.get("row_span") or 1))
        except (TypeError, ValueError):
            row_span = 1

        attributes = list(payload.get("attributes") or [])
        characters = list(payload.get("character_candidates") or [])
        consumed = 1
        if len(cells) >= 7 and row_span > 1:
            for offset in range(1, row_span):
                detail_index = index + offset
                if detail_index >= len(payloads):
                    break
                detail = dict(payloads[detail_index] or {})
                if not detail.get("is_buyer_detail"):
                    break
                attributes.extend(detail.get("attributes") or [])
                characters.extend(
                    detail.get("character_candidates") or [])
                consumed += 1

        payload["attributes"] = attributes
        payload["character_candidates"] = characters
        combined.append(payload)
        index += consumed

    return combined


def _split_game_server(subject_lines: List[str],
                       product_title: str) -> tuple[str, str]:
    normalized_title = _compact_text(product_title)
    lines = []
    for raw_line in subject_lines or []:
        line = _compact_text(str(raw_line).replace("베이톡", ""))
        if not line or line == normalized_title:
            continue
        lines.append(line)

    for line in reversed(lines):
        if " - " in line:
            game_name, server = line.rsplit(" - ", 1)
            return _compact_text(game_name), _compact_text(server)
    return "", ""


def _parse_order_row_payload(payload: dict) -> Optional[dict]:
    """把浏览器中一次性读取的订单行数据转换为平台原始订单。"""
    cells = list(payload.get("cells") or [])
    if len(cells) == 1 and "없습니다" in str(cells[0]):
        return None
    if len(cells) < 7:
        raise ValueError(f"订单行列数不足: {len(cells)}")

    item_match = re.search(r"\b[SB]\d+\b", str(cells[0]))
    if not item_match:
        raise ValueError("未提取到 ItemBay 商品编号")
    item_seq = item_match.group(0)

    attributes = list(payload.get("attributes") or [])
    data_tran_seq = _compact_text(payload.get("data_tran_seq"))
    if data_tran_seq:
        attributes.append(f"iTranSeq={data_tran_seq}")
    transaction_id = _extract_transaction_id(attributes)
    source_order_no = transaction_id or item_seq

    product_title = _compact_text(payload.get("title_link_text"))
    subject_lines = list(payload.get("subject_lines") or [])
    if not product_title:
        for line in subject_lines:
            candidate = _compact_text(str(line).replace("베이톡", ""))
            if candidate and " - " not in candidate:
                product_title = candidate
                break
    if not product_title:
        raise ValueError("未提取到商品标题")

    game_name, server = _split_game_server(
        subject_lines, product_title)
    if not game_name or not server:
        raise ValueError("未从商品标题列提取到游戏和区服")

    progress_text = str(cells[5] or "")
    character = _extract_character_name(
        list(payload.get("character_candidates") or []),
        progress_text,
    )
    has_delivery_action = bool(payload.get("has_delivery_action"))
    if has_delivery_action:
        trade_status = "paid"
    elif any(marker in progress_text for marker in (
            "전달완료", "거래진행", "진행중")):
        trade_status = "trading"
    else:
        # 该表只展示买家付款后的销售进行中订单。
        trade_status = "paid"

    return {
        "order_no": source_order_no,
        "item_order_no": source_order_no,
        "transaction_id": transaction_id,
        "item_seq": item_seq,
        "game_name": game_name,
        "server_id": server,
        "item_type": _compact_text(cells[1]),
        "title": product_title,
        "trade_amount": _compact_text(cells[3]),
        "price": _compact_text(cells[4]),
        "character": character,
        "trade_status": trade_status,
        "state": trade_status,
    }


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


class ItembayOrderWorker(PageWorker):
    """订单 Worker：固定在销售进行页，定时刷新并提取订单。"""

    def __init__(self, session, stop_event, monitor: 'ItembayMonitor'):
        super().__init__(session, stop_event, name="ItembayOrder")
        self._monitor = monitor
        self._relogin_failures = 0
        self._next_relogin_at = 0.0
        self._relogin_disabled = False
        self._last_relogin_wait_log_at = 0.0

    async def run(self):
        cfg = self._monitor.get_order_cfg()
        refresh_interval = cfg.get("refresh_interval", 3)
        wait_timeout = cfg.get("wait_timeout", 10000)
        print(
            f"[{self._log_tag}] 订单监控循环开始 "
            f"(interval={refresh_interval}s)"
        )
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
                reported = await self._monitor._collect_and_report_orders(
                    self.page)
                if reported > 0:
                    print(
                        f"[{self._log_tag}] 第{check_round}轮: "
                        f"上报 {reported} 个订单"
                    )
            except Exception as exc:
                print(f"[{self._log_tag}] 第{check_round}轮异常: {exc}")

            await self._reload_order_page(wait_timeout)
            await asyncio.sleep(refresh_interval)

    async def _ensure_order_page_ready(self, wait_timeout: int) -> bool:
        login_recovery = await self._recover_login_if_needed(
            wait_timeout, reason="订单检测前")
        if login_recovery is not None:
            return login_recovery

        navigated = False
        if "mybayStatusGiveListBySSL" not in self.page.url:
            committed = await self._goto_order_page(
                wait_timeout, reason="初始化订单页")
            navigated = True
            if not committed:
                raise RuntimeError("订单页初始化导航未提交")
            login_recovery = await self._recover_login_if_needed(
                wait_timeout, reason="进入订单页时")
            if login_recovery is not None:
                return login_recovery

        if await self._wait_order_table(wait_timeout):
            return True
        if navigated:
            raise RuntimeError("订单页导航后仍未出现订单表格")

        print(
            f"[{self._log_tag}] [订单页恢复] 关键区域未就绪，"
            "执行一次受控导航"
        )
        committed = await self._goto_order_page(
            wait_timeout, reason="恢复订单页")
        if committed and await self._wait_order_table(wait_timeout):
            return True
        raise RuntimeError("订单页在受控导航后仍未出现订单表格")

    async def _reload_order_page(self, wait_timeout: int):
        navigation_error = None
        if await self._recover_login_if_needed(
                wait_timeout, reason="刷新订单页前") is not None:
            return

        previous_origin = await _read_document_time_origin(self.page)
        committed = False
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
            print(
                f"[{self._log_tag}] [订单页恢复] reload 提交异常: "
                f"{exc}；复核新文档是否已提交"
            )
            committed = await _wait_for_document_change(
                self.page, previous_origin)

        if await self._recover_login_if_needed(
                wait_timeout, reason="刷新订单页后") is not None:
            return

        if committed and await self._wait_order_table(wait_timeout):
            if navigation_error is not None:
                print(
                    f"[{self._log_tag}] [订单页恢复] 页面实际已可用，"
                    "跳过重复 goto"
                )
            return

        print(
            f"[{self._log_tag}] [订单页恢复] 无法确认订单表格，"
            "执行一次受控 goto"
        )
        try:
            committed = await self._goto_order_page(
                wait_timeout, reason="刷新失败后的受控恢复")
        except Exception as exc:
            navigation_error = exc
            committed = False

        if await self._recover_login_if_needed(
                wait_timeout, reason="恢复订单页时") is not None:
            return
        if committed and await self._wait_order_table(wait_timeout):
            return

        message = "订单页刷新和受控恢复后仍未出现订单表格"
        if navigation_error is not None:
            raise RuntimeError(message) from navigation_error
        raise RuntimeError(message)

    async def _recover_login_if_needed(
            self, wait_timeout: int, reason: str) -> Optional[bool]:
        if not self._session.is_login_page(self.page.url):
            if self._relogin_failures or self._relogin_disabled:
                print(
                    f"[{self._log_tag}] 已恢复业务页面，"
                    "清除重新登录退避状态"
                )
                self._relogin_failures = 0
                self._next_relogin_at = 0.0
                self._relogin_disabled = False
            return None

        now = time.monotonic()
        if self._relogin_disabled:
            if now - self._last_relogin_wait_log_at >= 60:
                print(
                    f"[{self._log_tag}] 自动重新登录已暂停，"
                    "等待人工登录或重启监控"
                )
                self._last_relogin_wait_log_at = now
            return False
        if now < self._next_relogin_at:
            if now - self._last_relogin_wait_log_at >= 15:
                remaining = max(1, int(self._next_relogin_at - now))
                print(
                    f"[{self._log_tag}] 自动重新登录退避中，"
                    f"{remaining} 秒后再试"
                )
                self._last_relogin_wait_log_at = now
            return False

        print(
            f"[{self._log_tag}] 检测到 ItemBay 登录失效"
            f"（{reason}），当前页面={self.page.url}"
        )
        result = await self._session.relogin(self.page)
        if result.get("status") != "success":
            self._relogin_failures += 1
            message = result.get("message", "未知原因")
            if self._relogin_failures >= RELOGIN_MAX_ATTEMPTS:
                self._relogin_disabled = True
                print(
                    f"[{self._log_tag}] ItemBay 自动重新登录连续失败 "
                    f"{self._relogin_failures} 次，已暂停: {message}"
                )
                await play_alert_audio_async(
                    text=(
                        f"itemBay账号{self._session.account_id}"
                        "连续登录失败，已暂停自动登录，请检查凭证"
                    )
                )
                return False

            backoff_index = min(
                self._relogin_failures - 1,
                len(RELOGIN_BACKOFF_SECONDS) - 1,
            )
            backoff_seconds = RELOGIN_BACKOFF_SECONDS[backoff_index]
            self._next_relogin_at = time.monotonic() + backoff_seconds
            self._last_relogin_wait_log_at = 0.0
            print(
                f"[{self._log_tag}] ItemBay 自动重新登录失败"
                f"（第 {self._relogin_failures}/{RELOGIN_MAX_ATTEMPTS} 次）: "
                f"{message}；{int(backoff_seconds)} 秒后再试"
            )
            return False

        self._relogin_failures = 0
        self._next_relogin_at = 0.0
        self._relogin_disabled = False
        committed = await self._goto_order_page(
            wait_timeout, reason="重新登录后返回订单页")
        if not committed:
            raise RuntimeError("ItemBay 重新登录成功，但返回订单页未提交")
        if not await self._wait_order_table(wait_timeout):
            raise RuntimeError("ItemBay 重新登录成功，但订单表格仍未出现")
        return True

    async def _goto_order_page(self, wait_timeout: int, reason: str):
        print(f"[{self._log_tag}] [订单页导航] {reason}: {ORDER_LIST_URL}")
        previous_origin = await _read_document_time_origin(self.page)
        try:
            await self.page.goto(
                ORDER_LIST_URL,
                wait_until="commit",
                timeout=max(wait_timeout, MIN_COMMIT_TIMEOUT_MS),
            )
            return True
        except Exception as exc:
            if self.page.is_closed():
                raise
            print(
                f"[{self._log_tag}] [订单页导航] 提交异常: {exc}；"
                "复核新文档是否已提交"
            )
            return await _wait_for_document_change(
                self.page, previous_origin)

    async def _wait_order_table(self, wait_timeout: int) -> bool:
        ready_timeout = max(wait_timeout, MIN_READY_TIMEOUT_MS)
        try:
            await self.page.wait_for_selector(
                ORDER_TABLE_SELECTOR,
                state="attached",
                timeout=ready_timeout,
            )
            return True
        except Exception as exc:
            print(
                f"[{self._log_tag}] [订单页检测] 等待订单表格超时"
                f"（{ready_timeout}ms）: {exc}"
            )
            return False


class ItembayPresaleChatWorker(PageWorker):
    """售前咨询 Worker：轮询 BayTalk 未读数并持续语音提醒。"""

    def __init__(self, session, stop_event, monitor: 'ItembayMonitor'):
        super().__init__(session, stop_event, name="ItembayPresaleChat")
        self._monitor = monitor
        self._next_alert_at = 0.0
        self._last_unread_total = 0

    async def run(self):
        timeout = self._monitor.get_order_cfg().get(
            "wait_timeout", 10000)
        next_list_refresh_at = 0.0
        print(
            f"[{self._log_tag}] 售前咨询监控开始 "
            f"(poll={PRESALE_POLL_INTERVAL_SECONDS:.0f}s, "
            f"repeat={PRESALE_ALERT_INTERVAL_SECONDS:.0f}s)"
        )

        while not self.stopped:
            self._touch()
            if self._page_crashed:
                raise RuntimeError("BayTalk 售前总览页渲染进程已崩溃")

            try:
                now = time.monotonic()
                if now >= next_list_refresh_at:
                    await self._refresh_presale_list(timeout)
                    next_list_refresh_at = (
                        time.monotonic()
                        + PRESALE_LIST_REFRESH_INTERVAL_SECONDS
                    )

                inquiries = await self._read_unread_inquiries()
                await self._announce_if_due(inquiries, now=now)
            except Exception as exc:
                if self.page_failure_requires_rebuild(exc):
                    raise RuntimeError(
                        "BayTalk 售前总览页不可用，需要重建标签"
                    ) from exc
                print(
                    f"[{self._log_tag}] 售前咨询读取失败: {exc}；"
                    "下轮重新加载售前列表"
                )
                next_list_refresh_at = 0.0

            await asyncio.sleep(PRESALE_POLL_INTERVAL_SECONDS)

    async def _refresh_presale_list(self, timeout: int):
        if BAYTALK_LIST_URL not in self.page.url:
            await self._goto_chat_overview(timeout)

        tab = self.page.locator(PRESALE_TAB_SELECTOR).first
        if await tab.count() == 0:
            await self._goto_chat_overview(timeout)
            tab = self.page.locator(PRESALE_TAB_SELECTOR).first
        if await tab.count() == 0:
            raise RuntimeError("BayTalk 总览未找到交易前标签")

        # ItemBay 重载后默认回到交易中；点击交易前标签会通过站点自身
        # 的轻量请求刷新列表，比频繁整页 reload 更不容易触发渲染崩溃。
        await tab.click(timeout=max(timeout, MIN_COMMIT_TIMEOUT_MS))
        await self.page.wait_for_selector(
            PRESALE_LIST_SELECTOR,
            state="attached",
            timeout=max(timeout, MIN_READY_TIMEOUT_MS),
        )

    async def _goto_chat_overview(self, timeout: int):
        print(f"[{self._log_tag}] 导航到售前聊天总览: {BAYTALK_LIST_URL}")
        await self.page.goto(
            BAYTALK_LIST_URL,
            wait_until="domcontentloaded",
            timeout=max(timeout, MIN_COMMIT_TIMEOUT_MS),
        )
        if self._session.is_login_page(self.page.url):
            raise RuntimeError("ItemBay 登录失效，等待订单 Worker 恢复登录")

    async def _read_unread_inquiries(self) -> List[dict]:
        rows = self.page.locator(PRESALE_ROW_SELECTOR)
        payloads = await rows.evaluate_all("""
            rows => rows.map(row => {
                const unreadBox = row.querySelector(
                    '.info_game .ml-auto'
                );
                const unreadCandidates = unreadBox
                    ? Array.from(unreadBox.querySelectorAll('*'))
                        .filter(node => !node.classList.contains('blind'))
                        .flatMap(node => [
                            node.innerText || '',
                            node.getAttribute('data-count') || '',
                            node.getAttribute('data-unread-count') || '',
                            node.getAttribute('aria-label') || '',
                            node.getAttribute('title') || ''
                        ])
                    : [];
                return {
                    talk_seq:
                        row.getAttribute('data-biitemtalkseq') || '',
                    item_seq:
                        row.getAttribute('data-isiitemseq') || '',
                    game_server: (
                        row.querySelector('.name_ganme')
                            ?.innerText || ''
                    ),
                    last_time: (
                        row.querySelector('.info_time span:last-child')
                            ?.innerText || ''
                    ),
                    unread_text: [
                        unreadBox?.innerText || '',
                        unreadBox?.getAttribute('data-count') || '',
                        unreadBox?.getAttribute(
                            'data-unread-count'
                        ) || '',
                        ...unreadCandidates
                    ].join(' ')
                };
            })
        """)
        return [
            inquiry
            for payload in payloads
            if (inquiry := _parse_presale_inquiry_payload(payload))
            is not None
        ]

    async def _announce_if_due(
            self, inquiries: List[dict], now: Optional[float] = None) -> bool:
        unread_total = sum(
            int(inquiry.get("unread_count") or 0)
            for inquiry in inquiries
        )
        if unread_total <= 0:
            if self._last_unread_total > 0:
                print(f"[{self._log_tag}] 售前未读咨询已清零，停止播报")
            self._last_unread_total = 0
            self._next_alert_at = 0.0
            return False

        self._last_unread_total = unread_total
        current = time.monotonic() if now is None else now
        if current < self._next_alert_at:
            return False

        # conversation_count = len(inquiries)
        message = (
            f"itemBay账号{self._session.account_id}收到售前消息咨询"
            # f"{conversation_count}个会话共{unread_total}条未读，"
            # "请及时回复"
        )
        print(f"[{self._log_tag}] {message}；未处理将持续重复播报")
        self._next_alert_at = current + PRESALE_ALERT_INTERVAL_SECONDS
        return bool(await play_alert_audio_async(text=message))


class ItembayRefreshWorker(PageWorker):
    """商品刷新 Worker：进入商品修改页并保存，使商品重新排到前列。"""

    def __init__(self, session, stop_event, monitor: 'ItembayMonitor'):
        super().__init__(session, stop_event, name="ItembayRefresh")
        self._monitor = monitor
        self._last_refresh = datetime.datetime.now()

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
        print(f"[{self._log_tag}] 刷新就绪 (间隔={interval}s)")
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
                    result = await self._do_refresh(wait_timeout)
                    self._last_refresh = datetime.datetime.now()
                    await self._sync_sales_products(wait_timeout)
                    actions_on_page += 1

                    if actions_on_page >= REFRESH_PAGE_MAX_ACTIONS:
                        await self.recycle_page(
                            f"上架页已执行 {actions_on_page} 次刷新，"
                            "主动释放页面内存"
                        )
                        await self._ensure_refresh_page_ready(wait_timeout)
                        actions_on_page = 0
                except Exception as exc:
                    print(f"[{self._log_tag}] 刷新或销售商品快照同步异常: {exc}")
                    if self.page_failure_requires_rebuild(exc):
                        raise RuntimeError(
                            "上架页已不可用，需要重建标签"
                        ) from exc
            await asyncio.sleep(5)

    async def _do_refresh(self, timeout: int) -> str:
        await self._prepare_refresh_action_page(timeout)

        last_link = self.page.locator(LAST_PAGE_SELECTOR)
        last_count = await last_link.count()
        if last_count > 0:
            href = await last_link.first.get_attribute("href")
            if href and href != self.page.url:
                print(f"[{self._log_tag}] 跳转末页: {href}")
                await self._goto_refresh_page(
                    href, timeout, reason="刷新-进入末页")
        else:
            print(f"[{self._log_tag}] 当前上架列表没有末页链接")

        edit_links = self.page.locator(
            f"{REFRESH_ROW_SELECTOR} {EDIT_BUTTON_SELECTOR}")
        edit_count = await edit_links.count()
        print(f"[{self._log_tag}] 可见商品修改按钮: {edit_count}")
        if edit_count == 0:
            return "nothing_to_refresh"

        target = None
        target_action = None
        for index in range(edit_count - 1, -1, -1):
            edit_link = edit_links.nth(index)
            action = _parse_edit_action(
                await edit_link.get_attribute("onclick") or "")
            if action is None:
                continue
            if action["sell_status"] == 7:
                continue
            target = edit_link
            target_action = action
            break

        if target is None:
            print(f"[{self._log_tag}] 当前没有可修改的上架商品")
            return "nothing_to_refresh"

        print(
            f"[{self._log_tag}] 进入商品修改页: "
            f"item_seq={target_action['item_seq']}, "
            f"division={target_action['division']}"
        )
        await target.click(
            timeout=max(timeout, MIN_COMMIT_TIMEOUT_MS))
        await self._wait_edit_page_ready(
            target_action["item_seq"], timeout)

        submit = self.page.locator(EDIT_SUBMIT_SELECTOR).first
        previous_origin = await _read_document_time_origin(self.page)
        await submit.click(
            timeout=max(timeout, MIN_COMMIT_TIMEOUT_MS))
        return await self._wait_edit_save_result(
            previous_origin, target_action["item_seq"], timeout)

    async def _sync_sales_products(self, timeout: int) -> dict:
        first = await self._crawl_sales_products_once(timeout)
        second = await self._crawl_sales_products_once(timeout)
        if first != second:
            raise RuntimeError(
                "ItemBay 两次商品列表快照不一致，"
                "停止同步以避免误删")

        products = list(first.values())
        result = await asyncio.to_thread(
            self._monitor.reporter.sync_sales_products_snapshot,
            self._monitor.account_id,
            "itembay",
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

    async def _crawl_sales_products_once(
            self, timeout: int) -> dict:
        await self._goto_refresh_page(
            SELL_LIST_URL,
            timeout,
            reason="销售商品快照-返回第一页",
        )
        products = {}
        visited_urls = set()

        for page_index in range(1, MAX_SALES_PRODUCT_PAGES + 1):
            current_url = self.page.url
            if current_url in visited_urls:
                raise RuntimeError(
                    f"ItemBay 商品分页出现循环: {current_url}")
            visited_urls.add(current_url)

            page_products = await self._extract_sales_products_page()
            for product in page_products:
                product_id = product["platform_product_id"]
                if product_id in products:
                    raise RuntimeError(
                        f"ItemBay 快照出现重复商品 ID: {product_id}")
                products[product_id] = product

            next_link = self.page.locator(NEXT_PAGE_SELECTOR).first
            if await next_link.count() == 0:
                return dict(sorted(products.items()))
            next_url = await next_link.get_attribute("href") or ""
            if not next_url:
                raise RuntimeError("ItemBay 下一页链接缺少 href")
            next_url = urljoin(self.page.url, next_url)
            await self._goto_refresh_page(
                next_url,
                timeout,
                reason=f"销售商品快照-第{page_index + 1}页",
            )

        raise RuntimeError(
            f"ItemBay 商品分页超过 {MAX_SALES_PRODUCT_PAGES} 页")

    async def _extract_sales_products_page(self) -> List[dict]:
        snapshot = await self.page.locator(
            REFRESH_ROW_SELECTOR).evaluate_all("""
            rows => ({
                total_rows: rows.length,
                empty_rows: rows.filter(row => (
                    !row.querySelector(
                        'input[name="chkRemove"], a, button'
                    )
                    && row.querySelector('td[colspan]')
                    && (row.innerText || '').trim()
                )).length,
                inactive_rows: rows.filter(row => (
                    row.querySelector('input[name="chkRemove"]')
                    && !row.querySelector(
                        '.lt1_edit a[title="수정"]'
                    )
                )).length,
                products: rows
                    .filter(row => (
                        row.querySelector('input[name="chkRemove"]')
                        && row.querySelector(
                            '.lt1_edit a[title="수정"]'
                        )
                    ))
                    .map(row => ({
                    platform_product_id: (
                        row.querySelector(
                            'input[name="chkRemove"]'
                        )?.value || ''
                    ),
                    platform_item_type: (
                        row.querySelector('.lt1_sort')
                            ?.innerText || ''
                    ),
                    title: (
                        row.querySelector(
                            '.lt1_subject a[title]'
                        )?.getAttribute('title') || ''
                    ),
                    game_region: (
                        row.querySelector('.lt1_subject font')
                            ?.innerText || ''
                    ),
                    quantity_text: (
                        row.querySelector('.lt1_qty')
                            ?.innerText || ''
                    ),
                    price_text: (
                        row.querySelector('.lt1_price')
                            ?.innerText || ''
                    ),
                    platform_registered_at: (
                        row.querySelector('.gray_05')
                            ?.innerText || ''
                    )
                    }))
            })
        """)
        payloads = snapshot.get("products", [])
        recognized_rows = (
            len(payloads)
            + snapshot.get("empty_rows", 0)
            + snapshot.get("inactive_rows", 0)
        )
        if (snapshot.get("total_rows", 0) == 0
                or recognized_rows != snapshot.get("total_rows", 0)):
            raise RuntimeError(
                "ItemBay 上架表格没有商品行或明确空状态，"
                "停止同步以避免误删")
        return [
            _parse_sales_product_row_payload(payload)
            for payload in payloads
        ]

    async def _wait_edit_page_ready(
            self, item_seq: str, timeout: int) -> None:
        ready_timeout = max(timeout, MIN_READY_TIMEOUT_MS)
        try:
            await self.page.wait_for_selector(
                EDIT_SUBMIT_SELECTOR,
                state="visible",
                timeout=ready_timeout,
            )
        except Exception as exc:
            raise RuntimeError(
                f"商品 {item_seq} 修改页未出现保存按钮，"
                f"当前地址={self.page.url}"
            ) from exc
        if not any(path in self.page.url for path in EDIT_PAGE_PATHS):
            raise RuntimeError(
                f"商品 {item_seq} 未进入有效修改页，"
                f"当前地址={self.page.url}"
            )

    async def _wait_edit_save_result(
            self, previous_origin: Optional[float],
            item_seq: str, timeout: int) -> str:
        deadline = time.monotonic() + max(
            REFRESH_RESULT_TIMEOUT_SECONDS,
            max(timeout, MIN_COMMIT_TIMEOUT_MS) / 1000,
        )
        while time.monotonic() < deadline:
            if self.page.is_closed():
                raise RuntimeError("保存商品结果检查时页面已关闭")
            if self._session.is_login_page(self.page.url):
                raise RuntimeError("保存商品后检测到 ItemBay 登录失效")

            current_origin = await _read_document_time_origin(self.page)
            document_changed = (
                previous_origin is None
                or (
                    current_origin is not None
                    and current_origin != previous_origin
                )
            )
            if document_changed and SELL_LIST_URL in self.page.url:
                if await self._wait_refresh_table(timeout):
                    print(
                        f"[{self._log_tag}] 商品修改保存成功: "
                        f"item_seq={item_seq}"
                    )
                    return "refreshed"
            await asyncio.sleep(0.25)

        raise RuntimeError(
            f"商品 {item_seq} 保存后未返回有效上架列表，"
            f"当前地址={self.page.url}"
        )

    async def _prepare_refresh_action_page(self, timeout: int):
        if SELL_LIST_URL not in self.page.url:
            await self._goto_refresh_page(
                SELL_LIST_URL, timeout, reason="刷新-恢复上架页")
            return

        previous_origin = await _read_document_time_origin(self.page)
        committed = False
        try:
            await self.page.reload(
                wait_until="commit",
                timeout=max(timeout, MIN_COMMIT_TIMEOUT_MS),
            )
            committed = True
        except Exception as exc:
            if self.page.is_closed():
                raise
            print(
                f"[{self._log_tag}] [上架页刷新] reload 提交异常: "
                f"{exc}；复核新文档是否已提交"
            )
            committed = await _wait_for_document_change(
                self.page, previous_origin)

        if self._session.is_login_page(self.page.url):
            raise RuntimeError(
                "上架页刷新后检测到 ItemBay 登录失效，"
                "等待订单 Worker 处理登录恢复"
            )
        if committed and await self._wait_refresh_table(timeout):
            return

        await self._goto_refresh_page(
            SELL_LIST_URL, timeout, reason="刷新-受控恢复上架页")

    async def _ensure_refresh_page_ready(self, timeout: int):
        if SELL_LIST_URL in self.page.url:
            if await self._wait_refresh_table(timeout):
                return
        await self._goto_refresh_page(
            SELL_LIST_URL, timeout, reason="初始化上架页")

    async def _goto_refresh_page(
            self, url: str, timeout: int, reason: str):
        print(f"[{self._log_tag}] 导航到 ({reason}): {url}")
        previous_origin = await _read_document_time_origin(self.page)
        navigation_error = None
        try:
            await self.page.goto(
                url,
                wait_until="commit",
                timeout=max(timeout, MIN_COMMIT_TIMEOUT_MS),
            )
            committed = True
        except Exception as exc:
            if self.page.is_closed():
                raise
            navigation_error = exc
            print(
                f"[{self._log_tag}] [{reason}] 提交异常: {exc}；"
                "复核新文档是否已提交"
            )
            committed = await _wait_for_document_change(
                self.page, previous_origin)

        if not committed:
            message = f"{reason}导航未提交新文档"
            if navigation_error is not None:
                raise RuntimeError(message) from navigation_error
            raise RuntimeError(message)
        if await self._wait_refresh_table(timeout):
            return

        message = f"{reason}后仍未出现上架表格"
        if navigation_error is not None:
            raise RuntimeError(message) from navigation_error
        raise RuntimeError(message)

    async def _wait_refresh_table(self, timeout: int) -> bool:
        ready_timeout = max(timeout, MIN_READY_TIMEOUT_MS)
        try:
            await self.page.wait_for_selector(
                REFRESH_TABLE_SELECTOR,
                state="attached",
                timeout=ready_timeout,
            )
            return True
        except Exception as exc:
            print(
                f"[{self._log_tag}] [上架页检测] 等待上架表格超时"
                f"（{ready_timeout}ms）: {exc}"
            )
            return False


class ItembayMonitor(BaseOrderMonitor):
    """ItemBay 站点订单监控。"""

    tag = "itemBay"
    skip_login = False

    def get_order_cfg(self) -> dict:
        return {
            "my_page_url": SELL_LIST_URL,
            "my_page_selector": "",
            "wait_timeout": 10000,
            "refresh_interval": 3,
            "max_retries": 999,
        }

    def _get_workers(self) -> List[PageWorker]:
        if not self._session:
            raise RuntimeError("BrowserSession 未初始化")
        return [
            ItembayOrderWorker(
                self._session, self.stop_event, self),
            ItembayRefreshWorker(
                self._session, self.stop_event, self),
            ItembayPresaleChatWorker(
                self._session, self.stop_event, self),
        ]

    def _is_target_page(self, url: str) -> bool:
        return (
            SELL_LIST_URL in url
            or "mybayStatusGiveList" in url
        )

    def _is_on_collect_page(self, page) -> bool:
        return "mybayStatusGiveListBySSL" in page.url

    async def _extract_orders_from_table(
            self, page) -> OrderExtractionResult:
        table = page.locator(ORDER_TABLE_SELECTOR).first
        if await table.count() == 0:
            return OrderExtractionResult.failure(
                f"未找到 {ORDER_TABLE_SELECTOR} 订单表格")

        rows = page.locator(ORDER_ROW_SELECTOR)
        row_payloads = await rows.evaluate_all("""
            rows => rows.map(row => {
                const cells = Array.from(row.cells || []);
                const subject = cells[2];
                const titleLink = subject
                    ? subject.querySelector('a')
                    : null;
                const characterNodes = Array.from(
                    row.querySelectorAll(
                        '[onclick*="fncCharacterNameCopy"],'
                        + '[href*="fncCharacterNameCopy"],'
                        + '[data-character-name],'
                        + '[data-character],'
                        + '.buyer_info .hangul'
                    )
                );
                const attributeNodes = Array.from(
                    row.querySelectorAll('[href], [onclick]')
                );
                return {
                    cells: cells.map(
                        cell => (cell.innerText || '').trim()
                    ),
                    subject_lines: subject
                        ? (subject.innerText || '')
                            .split(/\\r?\\n/)
                            .map(value => value.trim())
                            .filter(Boolean)
                        : [],
                    title_link_text: titleLink
                        ? (titleLink.innerText || '').trim()
                        : '',
                    attributes: attributeNodes.flatMap(node => [
                        node.getAttribute('href') || '',
                        node.getAttribute('onclick') || ''
                    ]),
                    data_tran_seq:
                        row.getAttribute('data-tran-seq')
                        || row.getAttribute('data-transeq')
                        || '',
                    character_candidates:
                        characterNodes.map(node => ({
                            text: (node.innerText || '').trim(),
                            href: node.getAttribute('href') || '',
                            onclick: node.getAttribute('onclick') || '',
                            data_character_name:
                                node.getAttribute(
                                    'data-character-name'
                                ) || '',
                            data_character:
                                node.getAttribute(
                                    'data-character'
                                ) || ''
                        })),
                    has_delivery_action: Boolean(
                        row.querySelector(
                            '[onclick*="fncSetGiveItem"]'
                        )
                    ),
                    row_span: Number(
                        cells[0]?.getAttribute('rowspan') || 1
                    ),
                    is_buyer_detail: Boolean(
                        row.querySelector('td.buyer_info')
                    )
                };
            })
        """)
        payloads = _combine_order_row_payloads(row_payloads)
        orders = []
        candidate_rows = 0
        failed_rows = 0
        seen_order_ids = set()

        for index, payload in enumerate(payloads):
            counted_candidate = False
            try:
                if (
                    len(payload.get("cells") or []) == 1
                    and "없습니다" in str(payload["cells"][0])
                ):
                    continue
                candidate_rows += 1
                counted_candidate = True
                parsed = _parse_order_row_payload(payload)
                if parsed is None:
                    candidate_rows -= 1
                    continue
                order_no = parsed["order_no"]
                if order_no not in seen_order_ids:
                    orders.append(parsed)
                    seen_order_ids.add(order_no)
            except Exception as exc:
                if not counted_candidate:
                    candidate_rows += 1
                failed_rows += 1
                print(
                    f"[{self._log_tag}] 订单行 #{index} 提取失败: "
                    f"{exc}"
                )

        if candidate_rows > 0 and failed_rows == candidate_rows:
            return OrderExtractionResult.failure(
                f"订单表格存在 {candidate_rows} 条有效行，但全部解析失败")
        return OrderExtractionResult.success(orders)

    async def _build_normalized_order(
            self, page, order_data: dict):
        del page
        if not order_data.get("character"):
            print(
                f"[{self._log_tag}] 订单 "
                f"{order_data.get('order_no', '?')} "
                "未提取到买家角色名，停止上报"
            )
            return None

        try:
            quantity_value = parse_korean_amount(
                order_data.get("trade_amount", ""))
        except ValueError as exc:
            print(
                f"[{self._log_tag}] 订单 "
                f"{order_data.get('order_no', '?')} 数量解析失败: {exc}"
            )
            return None

        try:
            platform_price = parse_korean_amount(
                order_data.get("price", "").replace("원", ""))
        except ValueError:
            platform_price = Decimal("0")

        adapter = adapter_for("itembay")
        normalized = adapter.normalize(
            order_data,
            platform_order_time="",
            platform_price=platform_price,
            platform_item_type=order_data.get("item_type", ""),
            product_title=order_data.get("title", ""),
            quantity=int(quantity_value),
            sale_quantity=int(quantity_value),
        )
        if normalized is None:
            print(
                f"[{self._log_tag}] 适配器拒绝订单 "
                f"{order_data.get('order_no', '?')}: "
                f"{adapter.last_reject_reason}"
            )
        return normalized
