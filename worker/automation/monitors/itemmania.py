"""
ItemMania 订单监控子类（Async 多页面并行架构）。

Worker 分工：
  - OrderWorker：固定在 sell_ing.html，定时刷新页面，提取并上报订单
  - RefreshWorker：固定在 sell_regist.html 末页，定时点击「재등록」刷新上架
"""

import asyncio
import datetime
import os
import re
import tempfile
import time
from decimal import Decimal
from typing import List, Optional

from automation.audio_alert import play_alert_audio_async
from automation.order_monitor import BaseOrderMonitor
from automation.page_worker import PageWorker
from orders.adapters import parse_korean_amount, adapter_for, _parse_ko_units
from reporter import get_reporter

# ── 主事件循环引用（由 main.py 设置，供聊天发送跨线程调度） ──
_main_loop: Optional[asyncio.AbstractEventLoop] = None

# ── ItemMania 页面 URL 常量 ──
SELL_REGIST_URL = "https://www.itemmania.com/myroom/sell/sell_regist.html"
SELL_ING_URL = "https://www.itemmania.com/myroom/sell/sell_ing.html"
SELL_ING_VIEW_URL = "https://www.itemmania.com/myroom/sell/sell_ing_view.html"

# ── 韩文状态 → 英文映射 ──
STATUS_MAP = {
    "거래중": "trading",
    "입금대기": "paid",
    "판매완료": "completed",
}


def _parse_ko_number(text: str) -> int:
    """
    将含韩语单位的数字字符串转为实际整数。
    复用 adapters._parse_ko_units 的分层解析逻辑。
    例: '1만' → 10000, '5천만' → 50000000, '3억5천만' → 350000000
    """
    text = text.replace(' ', '').replace(',', '')
    if not text:
        return 0
    if text.isdigit():
        return int(text)
    return int(_parse_ko_units(text))


class ManiaOrderWorker(PageWorker):
    """订单 Worker：固定在 sell_ing.html，定时刷新提取订单。"""

    def __init__(self, session, stop_event, monitor: 'ItemmaniaMonitor'):
        super().__init__(session, stop_event, name="ManiaOrder")
        self._monitor = monitor

    async def run(self):
        cfg = self._monitor.get_order_cfg()
        refresh_interval = cfg.get("refresh_interval", 3)
        wait_timeout = cfg.get("wait_timeout", 10000)

        await self._navigate(SELL_ING_URL, "订单页")
        await self._wait_page_stable()

        print(f"[{self._log_tag}] 订单监控循环开始 (interval={refresh_interval}s)")
        check_round = 0

        while not self.stopped:
            check_round += 1
            self._touch()
            try:
                reported = await self._monitor._collect_and_report_orders(
                    self.page)
                if reported > 0:
                    print(f"[{self._log_tag}] "
                          f"第{check_round}轮: 上报 {reported} 个订单")
                elif check_round % 10 == 1:
                    pass
                    # print(f"[{self._log_tag}] "
                    #       f"第{check_round}轮: 无新订单")
            except Exception as e:
                print(f"[{self._log_tag}] 第{check_round}轮异常: {e}")

            # 刷新页面继续下一轮检测
            await self._safe_reload_or_navigate(SELL_ING_URL, wait_timeout)
            await asyncio.sleep(refresh_interval)


class ManiaRefreshWorker(PageWorker):
    """商品刷新 Worker：定时点击「재등록」。"""

    def __init__(self, session, stop_event, monitor: 'ItemmaniaMonitor'):
        super().__init__(session, stop_event, name="ManiaRefresh")
        self._monitor = monitor
        self._last_refresh = datetime.datetime.now()

    async def run(self):
        wait_timeout = self._monitor.get_order_cfg().get("wait_timeout", 10000)
        interval = 40

        await self._navigate(SELL_REGIST_URL, "刷新页")
        await self._wait_page_stable()
        print(f"[{self._log_tag}] 刷新就绪 (间隔={interval}s)")

        while not self.stopped:
            self._touch()
            elapsed = (datetime.datetime.now() -
                       self._last_refresh).total_seconds()
            if elapsed >= interval:
                try:
                    await self._do_refresh(wait_timeout)
                    self._last_refresh = datetime.datetime.now()
                except Exception as e:
                    print(f"[{self._log_tag}] 刷新异常: {e}")
            await asyncio.sleep(5)

    async def _do_refresh(self, timeout: int):
        """翻到最后一页 → 点击「재등록」。"""
        await self._navigate(SELL_REGIST_URL, "刷新-回到上架页",
                             wait_until="commit", skip_networkidle=True)

        # 1. 翻到最后一页
        try:
            await self.page.wait_for_selector(".cpnt.last", timeout=3000)
            last_link = await self.page.query_selector(".cpnt.last a")
            if last_link:
                href = await last_link.get_attribute("href")
                if href:
                    full_url = SELL_REGIST_URL + href
                    print(f"[{self._log_tag}] 跳转末页: {full_url}")
                    await self.page.goto(full_url,
                                         wait_until="commit",
                                         timeout=timeout)
                    await self.page.wait_for_timeout(1000)
        except Exception:
            print(f"[{self._log_tag}] 无分页元素")

        # 2. 点击最后一行「재등록」
        try:
            await self.page.wait_for_selector(
                ".g_blue_table.tb_list tbody tr", timeout=3000)
        except Exception:
            pass
        trs = await self.page.query_selector_all(
            ".g_blue_table.tb_list tbody tr")
        print(f"[{self._log_tag}] 上架商品: {len(trs)}")
        if len(trs) >= 1:
            btn = await trs[-1].query_selector(".flex_box .reregist")
            if btn:
                await btn.click()
                await self.page.wait_for_timeout(2000)
            else:
                print(f"[{self._log_tag}] 未找到 reregist 按钮")
        else:
            print(f"[{self._log_tag}] 无可刷新的商品")


class ItemmaniaMonitor(BaseOrderMonitor):
    """ItemMania 站点订单监控（Async 多页面并行）。"""

    tag = "mania"
    skip_login = False

    # 详情页缓存 TTL（秒）：同一订单在此时间内不重复打开详情页
    _DETAIL_CACHE_TTL = 60
    # 缓存最大条目数：超过后自动淘汰最旧条目
    _DETAIL_CACHE_MAX_SIZE = 500

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # trade_id → 上次抓取详情页的时间戳
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
            ManiaOrderWorker(
                self._session, self.stop_event, self,
            ),
            ManiaRefreshWorker(
                self._session, self.stop_event, self,
            ),
        ]

    def _is_target_page(self, url: str) -> bool:
        return SELL_REGIST_URL in url or SELL_ING_URL in url

    def _is_on_collect_page(self, page) -> bool:
        return "sell_ing" in page.url

    # ── 覆写：详情页优先的订单采集流程 ──

    async def _collect_and_report_orders(self, page) -> int:
        """
        详情页优先流程：
          1. 从表格提取 trade_id + 状态（轻量）
          2. 状态变更检测 + 去重
          3. asyncio.gather 并发打开所有新订单的详情页
          4. 以详情页数据为主构建 NormalizedOrder → 上报
        """
        if not self._is_on_collect_page(page):
            print(f"[{self._log_tag}] 不在采集目标页，跳过订单采集")
            return 0

        # 1. 从表格提取 trade_id + 状态
        table_orders = await self._extract_trade_ids_from_table(page)
        if not table_orders:
            self._consecutive_extraction_fails += 1
            print(f"[{self._log_tag}] 表格中无订单数据 "
                  f"(连续失败{self._consecutive_extraction_fails}次)")
            if self._consecutive_extraction_fails >= 3:
                await play_alert_audio_async(
                    text=f"{self.tag}账号{self.account_id} "
                         f"信息提取连续失败"
                         f"{self._consecutive_extraction_fails}次，"
                         f"请检查")
                self._consecutive_extraction_fails = 0
            return 0

        self._consecutive_extraction_fails = 0

        # ── 检测到订单即播报（与是否已上报无关） ──
        await play_alert_audio_async(
            text=f"{self.tag}账号{self.account_id} "
                 f"检测到{len(table_orders)}个订单")

        # 2. 检测订单状态变更
        for o in table_orders:
            order_no = o['order_no']
            new_state = o.get('state', '')
            old_state = self._known_order_statuses.get(order_no)
            if old_state and old_state != new_state:
                print(f"[{self._log_tag}] 📢 订单状态变更: {order_no} "
                      f"{old_state} → {new_state}")
                await play_alert_audio_async(
                    text=f"{self.tag}账号{self.account_id}: "
                         f"订单{order_no}状态变更为{new_state}")
            self._known_order_statuses[order_no] = new_state

        # 3. 过滤新订单
        new_orders = [
            o for o in table_orders
            if o['order_no'] not in self._reported_order_ids
        ]
        if not new_orders:
            # print(f"[{self._log_tag}] 所有 {len(table_orders)} 个订单"
            #       f"均已上报过")
            return 0

        # 4. 总控批量查重
        reporter = get_reporter()
        candidate_ids = [o['order_no'] for o in new_orders]
        try:
            existing_ids = await asyncio.to_thread(
                reporter.check_existing_orders,
                self.website_id, candidate_ids)
            if existing_ids:
                self._reported_order_ids.update(existing_ids)
                # print(f"[{self._log_tag}] 总控已有 {len(existing_ids)} 个"
                #       f"订单，跳过")
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

        # 5. 本地缓存过滤：跳过近期已抓取过详情页的订单
        self._cleanup_detail_cache()  # 先清理过期/溢出条目
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

        print(f"[{self._log_tag}] 真正新订单 {len(need_fetch)} 个，"
              f"开始并发抓取详情页"
              f"（缓存跳过 {len(trade_ids) - len(need_fetch)} 个）")

        # 6. 并发打开所有详情页，提取完整订单数据
        detail_results = await asyncio.gather(
            *[self._fetch_order_detail(tid) for tid in need_fetch]
        )

        # 定期清理过期缓存条目
        self._cleanup_detail_cache()

        # 预建 trade_id → state 映射（用于传入适配器）
        state_map = {o['order_no']: o.get('state', '') for o in new_orders}

        # 7. 构建 NormalizedOrder 并上报
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
                reporter.report_order_detected(
                    self.account_id, normalized)
                self._reported_order_ids.add(trade_id)
                # 上报成功后才写入缓存，失败时下次可重试
                self._detail_fetch_cache[trade_id] = time.time()
                reported += 1
            except Exception as e:
                print(f"[{self._log_tag}] 订单上报失败 "
                      f"(trade_id={trade_id}): {e}")

        return reported

    # ── 表格提取（轻量：仅 trade_id + 状态） ──

    async def _extract_trade_ids_from_table(self, page) -> list:
        """从 sell_ing.html 表格提取 trade_id 和状态。"""
        rows = page.locator('.g_blue_table.tb_list tbody tr')
        row_count = await rows.count()
        orders = []

        for i in range(row_count):
            try:
                row = rows.nth(i)
                tds = row.locator('td')
                if await tds.count() < 6:
                    continue
                if await tds.nth(0).locator('.empty_item').count() > 0:
                    continue

                # 从链接提取 trade_id
                link_el = tds.nth(2).locator('a')
                trade_id = ''
                if await link_el.count() > 0:
                    href = await link_el.get_attribute('href') or ''
                    m = re.search(r'id=(\d+)', href)
                    if m:
                        trade_id = m.group(1)
                if not trade_id:
                    continue

                # 提取状态
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
                print(f"[{self._log_tag}] 行 #{i} 提取失败: {e}")
                continue

        return orders

    # ── 详情页提取（完整订单数据） ──

    async def _fetch_order_detail(
            self, trade_id: str) -> Optional[dict]:
        """并发安全的详情页提取：打开新页面，提取完整订单数据。"""
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

            # 游戏 / 服务器 / 物品类型 + 平台订单时间
            try:
                cat_el = detail_page.locator('.trade_category')
                if await cat_el.count() > 0:
                    cat_text = (await cat_el.inner_text()).strip()
                    # "디아블로2:레저렉션 > 스탠다드 > 아이템 2026-07-15 17:02:47"
                    time_match = re.search(
                        r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})',
                        cat_text)
                    if time_match:
                        data['platform_order_time'] = (
                            time_match.group(1))
                    cat_clean = re.sub(
                        r'\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}',
                        '', cat_text).strip()
                    parts = [p.strip() for p in cat_clean.split('>')]
                    data['game_name'] = (
                        parts[0] if len(parts) > 0 else '')
                    data['server'] = (
                        parts[1] if len(parts) > 1 else '')
                    data['item_type'] = (
                        parts[2] if len(parts) > 2 else '')
            except Exception:
                pass

            # 标题 + 数量（从 trade_subject）
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

            # 价格（从 trade_info dl）
            try:
                dls = detail_page.locator(
                    '.default_info.trade_info dl')
                dl_count = await dls.count()
                for idx in range(dl_count):
                    dl = dls.nth(idx)
                    dt = (await dl.locator('dt').inner_text()
                          ).strip()
                    dd = (await dl.locator('dd').inner_text()
                          ).strip()
                    if '판매금액' in dt:
                        data['price'] = dd
            except Exception:
                pass

            # 买家角色名
            buyer = ''
            try:
                buyer_el = detail_page.locator(
                    'span.f_black.f_20').first
                if await buyer_el.count() > 0:
                    buyer = (await buyer_el.inner_text()).strip()
            except Exception:
                pass
            if not buyer:
                try:
                    result = await detail_page.evaluate("""
                        async () => {
                            const lis =
                                document.querySelectorAll('li');
                            for (const li of lis) {
                                const text = li.textContent || '';
                                const m = text.match(
                                    /구매자\\s*캐릭터명\\s*:\\s*(.+)/
                                );
                                if (m) return m[1].trim();
                            }
                            return '';
                        }
                    """)
                    buyer = (result or "").strip()
                except Exception:
                    pass
            data['buyer_name'] = buyer or f"buyer-{trade_id}"

            # 打印提取的完整订单原始数据
            print(
                f"[{self._log_tag}] 详情页提取完成 (trade_id={trade_id}):\n"
                f"  game={data.get('game_name', '?')}, "
                f"server={data.get('server', '?')}, "
                f"item={data.get('item_type', '?')}, "
                f"title={data.get('product_title', '?')}, "
                f"qty={data.get('quantity', '?')}, "
                f"sale_qty={data.get('sale_quantity', '?')}, "
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

    async def _build_from_detail(
            self, trade_id: str, detail: dict,
            state: str = ''):
        """用详情页数据构建 NormalizedOrder。"""
        # 价格解析
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
            platform_order_time=detail.get(
                'platform_order_time', ''),
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
              f"trade_id={trade_id}, "
              f"price={price_text}, "
              f"buyer={detail.get('buyer_name', '')[:10]}...")
        return normalized

    def _cleanup_detail_cache(self):
        """
        清理详情页缓存，防止内存溢出：
          1. 先移除所有超过 TTL 的过期条目
          2. 若仍超过 MAX_SIZE，按时间从旧到新淘汰，直到降至 MAX_SIZE 的 80%
        """
        now = time.time()
        # 第一步：移除过期条目
        expired = [
            tid for tid, ts in self._detail_fetch_cache.items()
            if now - ts > self._DETAIL_CACHE_TTL
        ]
        for tid in expired:
            del self._detail_fetch_cache[tid]

        # 第二步：容量超限时，淘汰最旧的条目
        if len(self._detail_fetch_cache) > self._DETAIL_CACHE_MAX_SIZE:
            # 按时间戳排序，保留最新的 80%
            sorted_items = sorted(
                self._detail_fetch_cache.items(), key=lambda x: x[1])
            target_size = int(self._DETAIL_CACHE_MAX_SIZE * 0.8)
            to_remove = len(sorted_items) - target_size
            for tid, _ in sorted_items[:to_remove]:
                del self._detail_fetch_cache[tid]


# ═══════════════════════════════════════════════════════════
# 聊天发送（ItemMania 招呼功能）
# ═══════════════════════════════════════════════════════════


def set_main_loop(loop: asyncio.AbstractEventLoop):
    """存储主事件循环引用，供跨线程调度。"""
    global _main_loop
    _main_loop = loop


def send_web_chat(account_id: int, chat_url: str, scripts: list) -> dict:
    """同步入口：向 ItemMania 聊天页面发送招呼消息，阻塞直到完成。

    Args:
        account_id: 账号 ID（定位浏览器会话）
        chat_url:  聊天页面完整 URL
        scripts:   话术列表 [{"content": "...", "image_url": "..."}, ...]

    Returns:
        {"success": bool, "message": str}
    """
    from automation.browser_session import BrowserSession

    print(f"[ChatSender] 开始发送招呼 account_id={account_id}, chat_url={chat_url}, 话术条数={len(scripts)}")

    if _main_loop is None:
        print("[ChatSender] 失败: event loop 未初始化")
        return {"success": False, "message": "event loop 未初始化"}

    # 先同步暂停 Worker，避免事件循环被 Worker 长操作占满时协程无法调度
    session = BrowserSession.get_or_create(account_id=account_id)
    if session._context is None:
        print(f"[ChatSender] 失败: 浏览器会话未初始化 account_id={account_id}")
        return {"success": False, "message": "浏览器会话未初始化"}
    session.acquire_chat_sender()
    print(f"[ChatSender] 已同步暂停 Worker account_id={account_id}")

    future = asyncio.run_coroutine_threadsafe(
        _do_send_web_chat(account_id, chat_url, scripts),
        _main_loop,
    )
    try:
        result = future.result(timeout=120)
        print(f"[ChatSender] 招呼执行完成 account_id={account_id}, result={result}")
        return result
    except TimeoutError:
        future.cancel()
        print(f"[ChatSender] 失败: 招呼发送超时(120s) account_id={account_id}")
        return {"success": False, "message": "招呼发送超时（120s）"}
    except Exception as e:
        print(f"[ChatSender] 失败: 招呼执行异常 account_id={account_id}, error={e}")
        return {"success": False, "message": f"招呼执行异常: {e}"}
    finally:
        session.release_chat_sender()
        print(f"[ChatSender] 已同步恢复 Worker account_id={account_id}")


async def _do_send_web_chat(account_id: int, chat_url: str, scripts: list) -> dict:
    """Async 实现：打开聊天页面 → 逐条发送 → 关闭页面。
    注意：acquire/release_chat_sender 已由外层 send_web_chat 同步调用。"""
    from automation.browser_session import BrowserSession

    # ── URL 校验 ──
    if not chat_url or "itemmania.com" not in chat_url:
        print(f"[ChatSender] 失败: 无效的聊天URL account_id={account_id}, url={chat_url}")
        return {"success": False, "message": "无效的聊天URL"}

    session = BrowserSession.get_or_create(account_id=account_id)
    if session._context is None:
        print(f"[ChatSender] 失败: 浏览器会话未初始化 account_id={account_id}")
        return {"success": False, "message": "浏览器会话未初始化"}

    print(f"[ChatSender] 获取浏览器会话成功 account_id={account_id}")

    page = None
    try:
        # 使用 claim_page 获取页面
        page = await session.claim_page()
        print(f"[ChatSender] 已 claim_page account_id={account_id}")

        # 打开聊天页面
        print(f"[ChatSender] 打开聊天页面: {chat_url}")
        await page.goto(chat_url, wait_until="commit", timeout=10000)
        print(f"[ChatSender] 页面 commit 完成")
        await page.wait_for_timeout(500)

        # 等待输入框和发送按钮就绪（带重试）
        input_ready = False
        for attempt in range(2):
            try:
                await page.wait_for_selector("#write_chat", timeout=5000)
                await page.wait_for_selector("#send_btn", timeout=2000)
                input_ready = True
                print(f"[ChatSender] 输入框 #write_chat 和发送按钮 #send_btn 已就绪")
                break
            except Exception:
                print(f"[ChatSender] 第{attempt+1}次等待元素失败，尝试重试...")
                await page.wait_for_timeout(1000)

        if not input_ready:
            print(f"[ChatSender] 失败: 聊天页面加载超时，输入框或发送按钮未找到")
            return {"success": False, "message": "聊天页面加载超时，输入框或发送按钮未找到"}

        # 逐条发送
        print(f"[ChatSender] 开始逐条发送话术，共{len(scripts)}条")
        for i, item in enumerate(scripts):
            image_url = item.get("image_url", "")
            content = item.get("content", "")
            print(f"[ChatSender] 处理第{i+1}/{len(scripts)}条: content_len={len(content)}, has_image={bool(image_url)}")

            # 先发图片
            if image_url:
                try:
                    await _send_image_via_chat(page, image_url)
                except Exception as e:
                    print(f"[ChatSender] 图片发送失败 (第{i+1}条): {e}")

            # 再发文字
            if content:
                await page.evaluate('''(selector, value) => {
                    const el = document.querySelector(selector);
                    if (el) {
                        el.value = value;
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                }''', "#write_chat", content)
                await page.locator("#send_btn").click(force=True, timeout=5000)
                await page.wait_for_timeout(600)
                print(f"[ChatSender] 第{i+1}条文字已发送: {content[:30]}{'...' if len(content) > 30 else ''}")
            elif not image_url:
                print(f"[ChatSender] 第{i+1}条无内容，跳过")

        print(f"[ChatSender] 所有招呼已发送 (共{len(scripts)}条)")
        return {"success": True, "message": "招呼发送成功"}

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[ChatSender] 异常退出: {e}")
        return {"success": False, "message": f"招呼执行异常: {e}"}
    finally:
        if page:
            try:
                await page.close()
                print(f"[ChatSender] 聊天页面已关闭 account_id={account_id}")
            except Exception:
                pass


async def _send_image_via_chat(page, image_url: str):
    """下载图片并通过聊天页面的文件上传发送。"""
    import requests

    print(f"[ChatSender] 开始下载图片: {image_url}")

    def _download():
        resp = requests.get(image_url, timeout=15)
        resp.raise_for_status()
        print(f"[ChatSender] 图片下载完成, size={len(resp.content)} bytes")
        return resp.content

    try:
        img_data = await asyncio.to_thread(_download)
    except Exception as e:
        print(f"[ChatSender] 图片下载失败: {e}")
        raise

    ext = _guess_ext(image_url)
    print(f"[ChatSender] 图片写入临时文件 ext={ext}")
    tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
    try:
        tmp.write(img_data)
        tmp.close()

        # 确认上传控件存在
        file_input = page.locator("#attach_layer input[type=file]")
        if await file_input.count() == 0:
            raise RuntimeError("上传控件 #attach_layer input[type=file] 未找到")
        await file_input.set_input_files(tmp.name)
        print(f"[ChatSender] 文件已选择到上传控件")

        await page.wait_for_timeout(1000)

        # 确认发送按钮存在且可见
        send_btn = page.locator("#attach_layer .btn_send")
        if await send_btn.count() == 0:
            raise RuntimeError("图片发送按钮 #attach_layer .btn_send 未找到")
        await send_btn.click()
        await page.wait_for_timeout(800)
        print(f"[ChatSender] 图片发送按钮已点击")

        # 关闭 attach_layer 弹层
        close_btn = page.locator("#attach_layer .close")
        if await close_btn.count() > 0 and await close_btn.is_visible():
            await close_btn.click()
            await page.wait_for_timeout(300)
            print(f"[ChatSender] attach_layer 已关闭")

        print(f"[ChatSender] 图片已发送: {image_url}")
    finally:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass


def _guess_ext(url: str) -> str:
    """从 URL 推测文件扩展名。"""
    url_lower = url.lower()
    if ".png" in url_lower:
        return ".png"
    if ".jpg" in url_lower or ".jpeg" in url_lower:
        return ".jpg"
    if ".webp" in url_lower:
        return ".webp"
    if ".gif" in url_lower:
        return ".gif"
    return ".png"
