"""
ItemMania 订单监控子类（Async 多页面并行架构）。

Worker 分工：
  - OrderWorker：固定在 sell_ing.html，定时刷新页面，提取并上报订单
  - RefreshWorker：固定在 sell_regist.html 末页，定时点击「재등록」刷新上架
"""
import asyncio
import datetime
import re
import time
from decimal import Decimal
from typing import List, Optional

from monitor.monitoring.base import BaseOrderMonitor
from monitor.monitoring.extraction import OrderExtractionResult
from monitor.monitoring.worker import PageWorker
from monitor.orders.adapters import parse_korean_amount, adapter_for, _parse_ko_units
from monitor.browser.audio import play_alert_audio_async

# ── ItemMania 页面 URL 常量 ──
SELL_REGIST_URL = "https://www.itemmania.com/myroom/sell/sell_regist.html"
SELL_ING_URL = "https://www.itemmania.com/myroom/sell/sell_ing.html"
SELL_ING_VIEW_URL = "https://www.itemmania.com/myroom/sell/sell_ing_view.html"
COUPON_ADD_PATH = "/myroom/coupon/add_reg.html"

ORDER_TABLE_SELECTOR = ".g_blue_table.tb_list"
REFRESH_TABLE_SELECTOR = ".g_blue_table.tb_list"
REFRESH_ROW_SELECTOR = ".g_blue_table.tb_list tbody tr"
MIN_COMMIT_TIMEOUT_MS = 15000
MIN_READY_TIMEOUT_MS = 20000
COMMIT_GRACE_SECONDS = 3.0
REFRESH_RESULT_TIMEOUT_SECONDS = 15.0
REFRESH_PAGE_MAX_ACTIONS = 30
RELOGIN_MAX_ATTEMPTS = 3
RELOGIN_BACKOFF_SECONDS = (30.0, 120.0)

# ── 韩文状态 → 英文映射 ──
STATUS_MAP = {
    "거래중": "trading",
    "입금대기": "paid",
    "판매완료": "completed",
}


def _parse_ko_number(text: str) -> int:
    """将含韩语单位的数字字符串转为实际整数。"""
    text = text.replace(' ', '').replace(',', '')
    if not text:
        return 0
    if text.isdigit():
        return int(text)
    return int(_parse_ko_units(text))


async def _read_document_time_origin(page) -> Optional[float]:
    """读取当前文档代次；导航成功后 performance.timeOrigin 会变化。"""
    try:
        return float(await page.evaluate("performance.timeOrigin"))
    except Exception:
        return None


async def _wait_for_document_change(page, previous_origin: Optional[float]) -> bool:
    """导航 API 超时时，短暂复核新文档是否其实已经提交。"""
    if previous_origin is None:
        return False
    loop = asyncio.get_running_loop()
    deadline = loop.time() + COMMIT_GRACE_SECONDS
    while loop.time() < deadline:
        current_origin = await _read_document_time_origin(page)
        if current_origin is not None and current_origin != previous_origin:
            return True
        await asyncio.sleep(0.25)
    return False


class ManiaOrderWorker(PageWorker):
    """订单 Worker：固定在 sell_ing.html，定时刷新提取订单。"""

    def __init__(self, session, stop_event, monitor: 'ItemmaniaMonitor'):
        super().__init__(session, stop_event, name="ManiaOrder")
        self._monitor = monitor
        self._relogin_failures = 0
        self._next_relogin_at = 0.0
        self._relogin_disabled = False
        self._last_relogin_wait_log_at = 0.0

    async def run(self):
        cfg = self._monitor.get_order_cfg()
        refresh_interval = cfg.get("refresh_interval", 3)
        wait_timeout = cfg.get("wait_timeout", 10000)

        print(f"[{self._log_tag}] 订单监控循环开始 (interval={refresh_interval}s)")
        check_round = 0

        while not self.stopped:
            check_round += 1
            self._touch()
            if not await self._ensure_order_page_ready(wait_timeout):
                await asyncio.sleep(refresh_interval)
                continue
            try:
                reported = await self._monitor._collect_and_report_orders(
                    self.page)
                if reported > 0:
                    print(f"[{self._log_tag}] "
                          f"第{check_round}轮: 上报 {reported} 个订单")
                elif check_round % 10 == 1:
                    pass
            except Exception as e:
                print(f"[{self._log_tag}] 第{check_round}轮异常: {e}")

            await self._reload_order_page(wait_timeout)
            await asyncio.sleep(refresh_interval)

    async def _ensure_order_page_ready(self, wait_timeout: int) -> bool:
        """进入订单页；登录恢复等待期间返回 False，让调用方跳过本轮抓取。"""
        login_recovery = await self._recover_login_if_needed(
            wait_timeout, reason="订单检测前")
        if login_recovery is not None:
            return login_recovery

        navigated = False
        if SELL_ING_URL not in self.page.url:
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

        print(f"[{self._log_tag}] [订单页恢复] 当前页面关键区域未就绪，"
              "执行一次受控导航")
        committed = await self._goto_order_page(
            wait_timeout, reason="恢复订单页")
        if committed and await self._wait_order_table(wait_timeout):
            return True

        raise RuntimeError("订单页在受控导航后仍未出现订单表格")

    async def _reload_order_page(self, wait_timeout: int):
        """刷新订单页；提交超时后先复核页面，避免连续 reload + goto。"""
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
        except Exception as e:
            if self.page.is_closed():
                raise
            navigation_error = e
            print(f"[{self._log_tag}] [订单页恢复] reload 提交阶段异常: "
                  f"{e}；先确认新文档是否已经提交")
            committed = await _wait_for_document_change(
                self.page, previous_origin)

        if await self._recover_login_if_needed(
                wait_timeout, reason="刷新订单页后") is not None:
            return

        if committed and await self._wait_order_table(wait_timeout):
            if navigation_error is not None:
                print(f"[{self._log_tag}] [订单页恢复] 页面实际已可用，"
                      "已跳过重复 goto")
            return

        if committed:
            print(f"[{self._log_tag}] [订单页恢复] 新文档已提交但订单表格"
                  "仍未出现，执行一次受控 goto")
        else:
            print(f"[{self._log_tag}] [订单页恢复] 刷新未提交新文档，"
                  "执行一次受控 goto")
        try:
            committed = await self._goto_order_page(
                wait_timeout, reason="刷新失败后的受控恢复")
        except Exception as e:
            navigation_error = e
            committed = False

        if await self._recover_login_if_needed(
                wait_timeout, reason="恢复订单页时") is not None:
            return

        if committed and await self._wait_order_table(wait_timeout):
            print(f"[{self._log_tag}] [订单页恢复] 受控 goto 后页面已恢复")
            return

        message = "订单页刷新和受控恢复后仍未出现订单表格"
        if navigation_error is not None:
            raise RuntimeError(message) from navigation_error
        raise RuntimeError(message)

    async def _recover_login_if_needed(
            self, wait_timeout: int, reason: str) -> Optional[bool]:
        """返回 None 表示无需恢复、True 表示已恢复、False 表示等待后续重试。"""
        if not self._session.is_login_page(self.page.url):
            if self._relogin_failures or self._relogin_disabled:
                print(f"[{self._log_tag}] 已观察到业务页面，清除重新登录退避状态")
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
            f"[{self._log_tag}] 检测到 ItemMania 登录失效"
            f"（{reason}），当前页面={self.page.url}"
        )
        result = await self._session.relogin(self.page)
        if result.get("status") != "success":
            self._relogin_failures += 1
            message = result.get("message", "未知原因")
            if self._relogin_failures >= RELOGIN_MAX_ATTEMPTS:
                self._relogin_disabled = True
                print(
                    f"[{self._log_tag}] ItemMania 自动重新登录连续失败 "
                    f"{self._relogin_failures} 次，已暂停自动尝试: {message}"
                )
                await play_alert_audio_async(
                    text=(
                        f"mania账号{self._session.account_id}连续登录失败，"
                        "已暂停自动登录，请检查凭证并手动登录"
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
                f"[{self._log_tag}] ItemMania 自动重新登录失败"
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
            raise RuntimeError("ItemMania 重新登录成功，但返回订单页未提交")
        if not await self._wait_order_table(wait_timeout):
            raise RuntimeError("ItemMania 重新登录成功，但订单表格仍未出现")

        print(f"[{self._log_tag}] ItemMania 自动重新登录并恢复订单页成功")
        return True

    async def _goto_order_page(self, wait_timeout: int, reason: str):
        """只等待导航提交，页面是否可用由订单表格单独判断。"""
        print(f"[{self._log_tag}] [订单页导航] {reason}: {SELL_ING_URL}")
        previous_origin = await _read_document_time_origin(self.page)
        try:
            await self.page.goto(
                SELL_ING_URL,
                wait_until="commit",
                timeout=max(wait_timeout, MIN_COMMIT_TIMEOUT_MS),
            )
            return True
        except Exception as e:
            if self.page.is_closed():
                raise
            print(f"[{self._log_tag}] [订单页导航] 提交阶段异常: {e}；"
                  "短暂复核新文档是否已经提交")
            committed = await _wait_for_document_change(
                self.page, previous_origin)
            if committed:
                print(f"[{self._log_tag}] [订单页导航] 新文档实际已提交")
            return committed

    async def _wait_order_table(self, wait_timeout: int) -> bool:
        ready_timeout = max(wait_timeout, MIN_READY_TIMEOUT_MS)
        try:
            await self.page.wait_for_selector(
                ORDER_TABLE_SELECTOR,
                state="attached",
                timeout=ready_timeout,
            )
            return True
        except Exception as e:
            print(f"[{self._log_tag}] [订单页检测] 等待订单表格超时"
                  f"（{ready_timeout}ms）: {e}")
            return False


class ManiaRefreshWorker(PageWorker):
    """商品刷新 Worker：定时点击「재등록」。"""

    def __init__(self, session, stop_event, monitor: 'ItemmaniaMonitor'):
        super().__init__(session, stop_event, name="ManiaRefresh")
        self._monitor = monitor
        self._last_refresh = datetime.datetime.now()

    async def run(self):
        wait_timeout = self._monitor.get_order_cfg().get("wait_timeout", 10000)
        interval = 40

        await self._ensure_refresh_page_ready(wait_timeout)
        print(f"[{self._log_tag}] 刷新就绪 (间隔={interval}s)")
        actions_on_page = 0

        while not self.stopped:
            self._touch()
            if self._page_crashed:
                raise RuntimeError("上架页渲染进程已崩溃")
            elapsed = (datetime.datetime.now() -
                       self._last_refresh).total_seconds()
            if elapsed >= interval:
                try:
                    result = await self._do_refresh(wait_timeout)
                    self._last_refresh = datetime.datetime.now()
                    actions_on_page += 1
                    if result == "coupon_required":
                        message = (
                            f"mania账号{self._session.account_id}"
                            "重新上架次数不足，请购买"
                        )
                        print(
                            f"[{self._log_tag}] ItemMania 重新上架次数"
                            "已用完，已恢复到上架页并发出语音提醒"
                        )
                        await play_alert_audio_async(text=message)
                    if actions_on_page >= REFRESH_PAGE_MAX_ACTIONS:
                        await self.recycle_page(
                            f"上架页已执行 {actions_on_page} 次刷新，"
                            "主动释放页面内存"
                        )
                        await self._ensure_refresh_page_ready(wait_timeout)
                        actions_on_page = 0
                except Exception as e:
                    print(f"[{self._log_tag}] 刷新异常: {e}")
                    if self.page_failure_requires_rebuild(e):
                        raise RuntimeError(
                            "上架页已不可用，需要重建标签"
                        ) from e
            await asyncio.sleep(5)

    async def _do_refresh(self, timeout: int):
        """翻到最后一页 → 点击「재등록」。"""
        # OrderWorker 和 RefreshWorker 各自拥有独立 Page；这里不跨页面串行导航。
        await self._prepare_refresh_action_page(timeout)

        last_link = self.page.locator(".cpnt.last a").first
        if await last_link.count() > 0:
            href = await last_link.get_attribute("href")
            if href:
                full_url = SELL_REGIST_URL + href
                if full_url != self.page.url:
                    print(f"[{self._log_tag}] 跳转末页: {full_url}")
                    await self._goto_refresh_page(
                        full_url, timeout, reason="刷新-进入末页")
        else:
            print(f"[{self._log_tag}] 无分页元素")

        rows = self.page.locator(REFRESH_ROW_SELECTOR)
        row_count = await rows.count()
        print(f"[{self._log_tag}] 上架商品: {row_count}")
        if row_count >= 1:
            btn = rows.nth(row_count - 1).locator(
                ".flex_box .reregist").first
            if await btn.count() > 0:
                previous_origin = await _read_document_time_origin(
                    self.page)
                click_error = None
                try:
                    await btn.click(
                        timeout=max(timeout, MIN_COMMIT_TIMEOUT_MS))
                except Exception as e:
                    if self.page.is_closed():
                        raise
                    click_error = e
                    print(
                        f"[{self._log_tag}] 重新上架点击等待异常: {e}；"
                        "继续检查平台实际返回页面"
                    )

                result = await self._wait_refresh_result(
                    previous_origin, timeout)
                if click_error is not None:
                    print(
                        f"[{self._log_tag}] 点击调用虽超时，但已根据"
                        f"最终页面确认结果={result}"
                    )
                return result
            else:
                print(f"[{self._log_tag}] 未找到 reregist 按钮")
        else:
            print(f"[{self._log_tag}] 无可刷新的商品")
        return "nothing_to_refresh"

    async def _wait_refresh_result(
            self, previous_origin: Optional[float], timeout: int) -> str:
        """确认重新上架提交的最终落点，避免把优惠券页当作成功。"""
        deadline = time.monotonic() + max(
            REFRESH_RESULT_TIMEOUT_SECONDS,
            max(timeout, MIN_COMMIT_TIMEOUT_MS) / 1000,
        )
        while time.monotonic() < deadline:
            current_url = self.page.url
            if COUPON_ADD_PATH in current_url:
                print(
                    f"[{self._log_tag}] 重新上架未成功，ItemMania 返回"
                    f"优惠券登记页: {current_url}"
                )
                await self._goto_refresh_page(
                    SELL_REGIST_URL,
                    timeout,
                    reason="优惠券页-恢复上架页",
                )
                return "coupon_required"

            current_origin = await _read_document_time_origin(self.page)
            document_changed = (
                previous_origin is None
                or (
                    current_origin is not None
                    and current_origin != previous_origin
                )
            )
            if document_changed and SELL_REGIST_URL in current_url:
                if await self._wait_refresh_table(timeout):
                    print(f"[{self._log_tag}] 重新上架提交成功")
                    return "refreshed"

            if self.page.is_closed():
                raise RuntimeError("重新上架结果检查时页面已关闭")
            await asyncio.sleep(0.25)

        raise RuntimeError(
            f"重新上架提交后未进入有效结果页，当前地址={self.page.url}"
        )

    async def _prepare_refresh_action_page(self, timeout: int):
        """刷新当前上架列表；无法确认新文档时再执行一次受控导航。"""
        if SELL_REGIST_URL not in self.page.url:
            await self._goto_refresh_page(
                SELL_REGIST_URL, timeout, reason="刷新-恢复上架页")
            return

        previous_origin = await _read_document_time_origin(self.page)
        committed = False
        try:
            await self.page.reload(
                wait_until="commit",
                timeout=max(timeout, MIN_COMMIT_TIMEOUT_MS),
            )
            committed = True
        except Exception as e:
            if self.page.is_closed():
                raise
            print(
                f"[{self._log_tag}] [上架页刷新] reload 提交阶段异常: "
                f"{e}；短暂复核新文档是否已经提交"
            )
            committed = await _wait_for_document_change(
                self.page, previous_origin)

        if self._session.is_login_page(self.page.url):
            raise RuntimeError(
                "上架页刷新后检测到 ItemMania 登录失效，"
                "等待订单 Worker 处理登录恢复"
            )

        if committed and await self._wait_refresh_table(timeout):
            return

        print(
            f"[{self._log_tag}] [上架页刷新] 无法确认最新列表，"
            "执行一次受控导航"
        )
        await self._goto_refresh_page(
            SELL_REGIST_URL, timeout, reason="刷新-受控恢复上架页")

    async def _ensure_refresh_page_ready(self, timeout: int):
        if SELL_REGIST_URL in self.page.url:
            if await self._wait_refresh_table(timeout):
                return
        await self._goto_refresh_page(
            SELL_REGIST_URL, timeout, reason="初始化上架页")

    async def _goto_refresh_page(self, url: str, timeout: int, reason: str):
        """导航上架页并以业务表格判断可用，不等待 networkidle。"""
        print(f"[{self._log_tag}] 导航到 ({reason}): {url}")
        navigation_error = None
        previous_origin = await _read_document_time_origin(self.page)
        try:
            await self.page.goto(
                url,
                wait_until="commit",
                timeout=max(timeout, MIN_COMMIT_TIMEOUT_MS),
            )
            committed = True
        except Exception as e:
            if self.page.is_closed():
                raise
            navigation_error = e
            print(f"[{self._log_tag}] [{reason}] 提交阶段异常: {e}；"
                  "短暂复核新文档是否已经提交")
            committed = await _wait_for_document_change(
                self.page, previous_origin)

        if not committed:
            message = f"{reason}导航未提交新文档"
            if navigation_error is not None:
                raise RuntimeError(message) from navigation_error
            raise RuntimeError(message)

        if await self._wait_refresh_table(timeout):
            if navigation_error is not None:
                print(f"[{self._log_tag}] [{reason}] 页面实际已可用")
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
        except Exception as e:
            print(f"[{self._log_tag}] [上架页检测] 等待上架表格超时"
                  f"（{ready_timeout}ms）: {e}")
            return False


class ItemmaniaMonitor(BaseOrderMonitor):
    """ItemMania 站点订单监控（Async 多页面并行）。"""

    tag = "mania"
    skip_login = False

    _DETAIL_CACHE_TTL = 60
    _DETAIL_CACHE_MAX_SIZE = 500

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._detail_fetch_cache: dict = {}

    def get_order_cfg(self) -> dict:
        return {
            "my_page_url": SELL_REGIST_URL,
            "my_page_selector": (
                "#g_BODY > header > div > div.header-nav-wrapper "
                "> nav > a:nth-child(4)"
            ),
            "wait_timeout": 10000,
            "refresh_interval": 3,
            "max_retries": 999,
        }

    def _get_workers(self) -> List[PageWorker]:
        if not self._session:
            raise RuntimeError("BrowserSession 未初始化")
        return [
            ManiaOrderWorker(self._session, self.stop_event, self),
            ManiaRefreshWorker(self._session, self.stop_event, self),
        ]

    def _is_target_page(self, url: str) -> bool:
        return SELL_REGIST_URL in url or SELL_ING_URL in url

    def _is_on_collect_page(self, page) -> bool:
        return "sell_ing" in page.url

    # ── 覆写：详情页优先的订单采集流程 ──

    async def _collect_and_report_orders(self, page) -> int:
        """详情页优先流程：表格 → 去重 → 并发详情页 → 标准化上报。"""
        if not self._is_on_collect_page(page):
            print(f"[{self._log_tag}] 不在采集目标页，跳过")
            return 0

        extraction = await self._extract_trade_ids_from_table(page)
        if extraction.failed:
            self._consecutive_extraction_fails += 1
            print(f"[{self._log_tag}] 订单提取失败 "
                  f"(连续失败{self._consecutive_extraction_fails}次)。"
                  f"原因：{extraction.error}；解决方案：检查登录状态和 ItemMania 订单表格结构。")
            if self._consecutive_extraction_fails >= 3:
                await play_alert_audio_async(
                    text=f"{self.tag}账号{self.account_id} "
                         f"信息提取连续失败{self._consecutive_extraction_fails}次，请检查")
                self._consecutive_extraction_fails = 0
            return 0


        table_orders = extraction.orders
        if not table_orders:
            self._consecutive_extraction_fails = 0
            print(f"[{self._log_tag}] 订单表格正常，当前无订单")
            return 0

        self._consecutive_extraction_fails = 0
        await play_alert_audio_async(
            text=f"{self.tag}账号{self.account_id} "
                 f"检测到{len(table_orders)}个订单")

        for o in table_orders:
            order_no = o['order_no']
            new_state = o.get('state', '')
            old_state = self._known_order_statuses.get(order_no)
            if old_state and old_state != new_state:
                print(f"[{self._log_tag}] 订单状态变更: {order_no} "
                      f"{old_state} -> {new_state}")
                await play_alert_audio_async(
                    text=f"{self.tag}账号{self.account_id}: "
                         f"订单{order_no}状态变更为{new_state}")
            self._known_order_statuses[order_no] = new_state

        new_orders = [
            o for o in table_orders
            if o['order_no'] not in self._reported_order_ids
        ]
        if not new_orders:
            return 0

        candidate_ids = [o['order_no'] for o in new_orders]
        try:
            existing_ids = await asyncio.to_thread(
                self.reporter.check_existing_orders,
                self.website_id, candidate_ids)
            if existing_ids:
                self._reported_order_ids.update(existing_ids)
        except Exception as e:
            print(f"[{self._log_tag}] 总控查重失败，按全部新订单处理: {e}")
            existing_ids = set()

        new_orders = [
            o for o in new_orders
            if o['order_no'] not in existing_ids
        ]
        if not new_orders:
            print(f"[{self._log_tag}] 所有订单均已存在于总控")
            return 0

        trade_ids = [o['order_no'] for o in new_orders]

        self._cleanup_detail_cache()
        now = time.time()
        need_fetch = []
        for tid in trade_ids:
            last_fetch = self._detail_fetch_cache.get(tid, 0)
            if now - last_fetch < self._DETAIL_CACHE_TTL:
                print(f"[{self._log_tag}] trade_id={tid} "
                      f"详情页缓存未过期，跳过")
                continue
            need_fetch.append(tid)

        if not need_fetch:
            print(f"[{self._log_tag}] 所有新订单均在详情页缓存期内")
            return 0

        print(f"[{self._log_tag}] 真正新订单 {len(need_fetch)} 个，开始并发抓取详情页"
              f"（缓存跳过 {len(trade_ids) - len(need_fetch)} 个）")

        detail_results = await asyncio.gather(
            *[self._fetch_order_detail(tid) for tid in need_fetch]
        )

        self._cleanup_detail_cache()

        state_map = {o['order_no']: o.get('state', '') for o in new_orders}

        reported = 0
        for trade_id, detail_data in zip(need_fetch, detail_results):
            if detail_data is None:
                print(f"[{self._log_tag}] 详情页数据为空，跳过 "
                      f"trade_id={trade_id}")
                continue
            try:
                normalized = await self._build_from_detail(
                    trade_id, detail_data,
                    state=state_map.get(trade_id, ''))
                if normalized is None:
                    continue
                self.reporter.report_order_detected(
                    self.account_id, normalized)
                self._reported_order_ids.add(trade_id)
                self._detail_fetch_cache[trade_id] = time.time()
                reported += 1
            except Exception as e:
                print(f"[{self._log_tag}] 订单上报失败 "
                      f"(trade_id={trade_id}): {e}")

        return reported

    # ── 表格提取 ──

    async def _extract_trade_ids_from_table(self, page) -> OrderExtractionResult:
        """从 sell_ing.html 表格提取 trade_id 和状态。"""
        table = page.locator('.g_blue_table.tb_list').first
        if await table.count() == 0:
            return OrderExtractionResult.failure("未找到 .g_blue_table.tb_list 订单表格")

        rows = page.locator('.g_blue_table.tb_list tbody tr')
        row_count = await rows.count()
        orders = []
        candidate_rows = 0
        failed_rows = 0

        for i in range(row_count):
            candidate_rows += 1
            try:
                row = rows.nth(i)
                if await row.locator('.empty_item').count() > 0:
                    candidate_rows -= 1
                    continue
                tds = row.locator('td')
                if await tds.count() < 6:
                    failed_rows += 1
                    print(f"[{self._log_tag}] 行 #{i} 列数不足，无法提取订单")
                    continue

                link_el = tds.nth(2).locator('a')
                trade_id = ''
                if await link_el.count() > 0:
                    href = await link_el.get_attribute('href') or ''
                    m = re.search(r'id=(\d+)', href)
                    if m:
                        trade_id = m.group(1)
                if not trade_id:
                    failed_rows += 1
                    print(f"[{self._log_tag}] 行 #{i} 未提取到订单号")
                    continue

                status_el = tds.nth(5).locator(
                    '.btn_base, span').first
                status_raw = (
                    (await status_el.inner_text()).strip()
                    if await status_el.count() > 0 else ''
                )

                orders.append({
                    'order_no': trade_id,
                    'state': STATUS_MAP.get(status_raw, status_raw),
                })
            except Exception as e:
                failed_rows += 1
                print(f"[{self._log_tag}] 行 #{i} 提取失败: {e}")
                continue

        if candidate_rows > 0 and failed_rows == candidate_rows:
            return OrderExtractionResult.failure(
                f"订单表格存在 {candidate_rows} 条有效行，但全部解析失败")
        return OrderExtractionResult.success(orders)

    # ── 详情页提取 ──

    async def _fetch_order_detail(self, trade_id: str) -> Optional[dict]:
        """并发安全的详情页提取。"""
        detail_url = f"{SELL_ING_VIEW_URL}?id={trade_id}&type=sell"
        detail_page = None
        try:
            detail_page = await self._session.new_page()
            self._active_temp_pages.add(id(detail_page))
            await detail_page.goto(
                detail_url, wait_until="domcontentloaded",
                timeout=15000)
            await detail_page.wait_for_timeout(2000)
            try:
                await detail_page.wait_for_load_state(
                    "networkidle", timeout=10000)
            except Exception:
                pass

            data = {}

            try:
                cat_el = detail_page.locator('.trade_category')
                if await cat_el.count() > 0:
                    cat_text = (await cat_el.inner_text()).strip()
                    time_match = re.search(
                        r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})',
                        cat_text)
                    if time_match:
                        data['platform_order_time'] = time_match.group(1)
                    cat_clean = re.sub(
                        r'\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}',
                        '', cat_text).strip()
                    parts = [p.strip() for p in cat_clean.split('>')]
                    data['game_name'] = parts[0] if len(parts) > 0 else ''
                    data['server'] = parts[1] if len(parts) > 1 else ''
                    data['item_type'] = parts[2] if len(parts) > 2 else ''
            except Exception:
                pass

            try:
                subj_el = detail_page.locator('.trade_subject')
                if await subj_el.count() > 0:
                    subj_text = (await subj_el.inner_text()).strip()
                    qty_m = re.search(
                        r'\[수량\s*:\s*([\d,]+\s*[조억만천]?\s*(?:[\d,]+\s*[조억만천]?)*[\d,]*)\]',
                        subj_text)
                    if qty_m:
                        raw_qty = qty_m.group(1).strip()
                        qty_val = _parse_ko_number(raw_qty)
                        data['quantity'] = str(qty_val)
                        data['sale_quantity'] = str(qty_val)
                    data['product_title'] = re.sub(
                        r'\[수량\s*:\s*[^\]]*\]\s*', '', subj_text
                    ).strip()
            except Exception:
                pass

            try:
                dls = detail_page.locator(
                    '.default_info.trade_info dl')
                dl_count = await dls.count()
                for idx in range(dl_count):
                    dl = dls.nth(idx)
                    dt = (await dl.locator('dt').inner_text()).strip()
                    dd = (await dl.locator('dd').inner_text()).strip()
                    if '판매금액' in dt:
                        data['price'] = dd
            except Exception:
                pass

            buyer = ''
            try:
                buyer_li = detail_page.locator('li').filter(
                    has_text='구매자 캐릭터명').first
                buyer_el = buyer_li.locator('span.f_black.f_20').first
                if await buyer_el.count() > 0:
                    buyer = (await buyer_el.inner_text()).strip()
            except Exception:
                pass
            if not buyer:
                try:
                    result = await detail_page.evaluate("""
                        async () => {
                            const labels = document.querySelectorAll(
                                'span.f_gray3'
                            );
                            for (const label of labels) {
                                if (!(label.textContent || '').includes(
                                    '구매자 캐릭터명'
                                )) {
                                    continue;
                                }
                                const li = label.closest('li');
                                const value = li && li.querySelector(
                                    'span.f_black.f_20'
                                );
                                if (value) {
                                    return (value.textContent || '').trim();
                                }
                            }
                            return '';
                        }
                    """)
                    buyer = (result or "").strip()
                except Exception:
                    pass
            if not buyer:
                raise ValueError(
                    "详情页未提取到买家角色名，停止上报，避免生成伪造买家名"
                )
            data['buyer_name'] = buyer

            print(
                f"[{self._log_tag}] 详情页提取完成 (trade_id={trade_id}):\n"
                f"  game={data.get('game_name', '?')}, "
                f"server={data.get('server', '?')}, "
                f"item={data.get('item_type', '?')}, "
                f"title={data.get('product_title', '?')}, "
                f"qty={data.get('quantity', '?')}, "
                f"price={data.get('price', '?')}, "
                f"buyer={data.get('buyer_name', '?')}, "
                f"time={data.get('platform_order_time', '?')}"
            )

            return data

        except Exception as e:
            print(f"[{self._log_tag}] 详情页提取失败 "
                  f"(trade_id={trade_id}): {e}")
            return None
        finally:
            if detail_page:
                self._active_temp_pages.discard(id(detail_page))
                try:
                    await detail_page.close()
                except Exception:
                    pass

    # ── 标准化 ──

    async def _build_from_detail(self, trade_id: str, detail: dict,
                                 state: str = ''):
        """用详情页数据构建 NormalizedOrder。"""
        price_text = detail.get('price', '0')
        try:
            platform_price = parse_korean_amount(
                price_text.replace('원', ''))
        except ValueError:
            platform_price = Decimal('0')

        order_data = {
            'game_name': detail.get('game_name', ''),
            'server': detail.get('server', ''),
            'item_type': detail.get('item_type', ''),
            'order_no': trade_id,
            'state': state,
            'quantity': detail.get('quantity', ''),
            'product_title': detail.get('product_title', ''),
            'price': price_text,
            'buyer_name': detail.get('buyer_name', ''),
        }

        adapter = adapter_for("itemmania")
        normalized = adapter.normalize(
            order_data,
            platform_order_time=detail.get('platform_order_time', ''),
            platform_price=platform_price,
            platform_item_type=detail.get('item_type', ''),
            product_title=detail.get('product_title', ''),
            quantity=int(detail.get('quantity', '0') or '0'),
            sale_quantity=int(detail.get('sale_quantity', '0') or '0'),
        )
        if normalized is None:
            print(f"[{self._log_tag}] 适配器拒绝订单 "
                  f"(trade_id={trade_id}): "
                  f"{adapter.last_reject_reason}")
            return None

        print(f"[{self._log_tag}] 订单已上报: "
              f"trade_id={trade_id}, price={price_text}")
        return normalized

    def _cleanup_detail_cache(self):
        """清理详情页缓存，防止内存溢出。"""
        now = time.time()
        expired = [
            tid for tid, ts in self._detail_fetch_cache.items()
            if now - ts > self._DETAIL_CACHE_TTL
        ]
        for tid in expired:
            del self._detail_fetch_cache[tid]

        if len(self._detail_fetch_cache) > self._DETAIL_CACHE_MAX_SIZE:
            sorted_items = sorted(
                self._detail_fetch_cache.items(), key=lambda x: x[1])
            target_size = int(self._DETAIL_CACHE_MAX_SIZE * 0.8)
            to_remove = len(sorted_items) - target_size
            for tid, _ in sorted_items[:to_remove]:
                del self._detail_fetch_cache[tid]
