"""
ItemMania 订单监控子类（Async 多页面并行架构）。

Worker 分工：
  - DetectionWorker：固定在 sell_regist.html，AJAX 轮询订单数，有订单时通知提取
  - ExtractionWorker：收到信号后导航到 sell_ing.html，提取订单并上报总控
  - RefreshWorker：固定在 sell_regist.html 末页，定时点击「재등록」刷新上架

共享通信（asyncio.Event）：
  - detection_event: 检测到订单时 set
  - extraction_done_event: 提取完成后 set
"""

import asyncio
import datetime
import re
from decimal import Decimal
from typing import Optional, List

from automation.order_monitor import BaseOrderMonitor
from automation.page_worker import PageWorker
from automation.audio_alert import play_alert_audio
from orders.adapters import parse_korean_amount, adapter_for

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


class ManiaDetectionWorker(PageWorker):
    """订单检测 Worker：AJAX 轮询订单数。"""

    def __init__(self, session, stop_event, monitor: 'ItemmaniaMonitor',
                 detection_event: asyncio.Event,
                 extraction_done_event: asyncio.Event,
                 order_count_ref: dict):
        super().__init__(session, stop_event, name="ManiaDetect")
        self._monitor = monitor
        self._detection_event = detection_event
        self._extraction_done_event = extraction_done_event
        self._order_count_ref = order_count_ref

    async def run(self):
        cfg = self._monitor.get_order_cfg()
        refresh_interval = cfg.get("refresh_interval", 3)
        wait_timeout = cfg.get("wait_timeout", 10000)

        await self._navigate(SELL_REGIST_URL, "检测页")
        await self._wait_page_stable()

        print(f"[{self._log_tag}] 检测循环开始 (interval={refresh_interval}s)")
        check_round = 0

        while not self.stopped:
            check_round += 1
            self._touch()
            try:
                count = await self._ajax_detect()
                if count is None:
                    if check_round % 10 == 1:
                        print(f"[{self._log_tag}] "
                              f"第{check_round}轮: AJAX失败，刷新")
                    await self._safe_reload_or_navigate(SELL_REGIST_URL,
                                                        wait_timeout)
                    await asyncio.sleep(refresh_interval)
                    continue

                if count > 0:
                    self._order_count_ref['count'] = count
                    print(f"[{self._log_tag}] "
                          f"第{check_round}轮: {count} 个订单！")
                    tag = self._monitor.tag
                    acct = self._monitor.account_id
                    play_alert_audio(
                        text=f"{tag}账号{acct}: 检测到 {count} 个订单！")

                    # 通知 ExtractionWorker
                    self._extraction_done_event.clear()
                    self._detection_event.set()

                    # 等待提取完成
                    print(f"[{self._log_tag}] 等待提取完成...")
                    while not self.stopped:
                        try:
                            await asyncio.wait_for(
                                self._extraction_done_event.wait(),
                                timeout=1)
                            break
                        except asyncio.TimeoutError:
                            continue
                    print(f"[{self._log_tag}] 提取完成，恢复检测")
                    await self._safe_reload_or_navigate(SELL_REGIST_URL,
                                                        wait_timeout)
                else:
                    if check_round % 10 == 1:
                        print(f"[{self._log_tag}] "
                              f"第{check_round}轮: 无订单")

            except Exception as e:
                print(f"[{self._log_tag}] 第{check_round}轮异常: {e}")

            await asyncio.sleep(refresh_interval)

    async def _ajax_detect(self) -> Optional[int]:
        """AJAX 计数接口。"""
        js = """
        async () => {
            const resp = await fetch(
                '/myroom/_include/_ajax_trade_count.php?_=' + Date.now(), {
                    credentials: 'include',
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'Accept': 'application/json, text/javascript, */*; q=0.01',
                    },
                });
            if (!resp.ok) return {_err: 'HTTP ' + resp.status};
            const text = await resp.text();
            try {
                const data = JSON.parse(text);
                if (data.result === 'SUCCESS')
                    return data.trade_count.sell_ing;
                return -1;
            } catch (e) {
                return {_err: '非JSON响应', _preview: text.substring(0, 100)};
            }
        }
        """
        try:
            result = await self.page.evaluate(js)
            if isinstance(result, dict) and '_err' in result:
                print(f"[{self._log_tag}] AJAX失败: {result['_err']}, "
                      f"preview={result.get('_preview', 'N/A')}")
                return None
            if (result is not None and isinstance(result, (int, float))
                    and result >= 0):
                return int(result)
            return None
        except Exception as e:
            print(f"[{self._log_tag}] AJAX异常: {e}")
            return None


class ManiaExtractionWorker(PageWorker):
    """订单提取 Worker：收到信号后提取并上报订单。"""

    def __init__(self, session, stop_event, monitor: 'ItemmaniaMonitor',
                 detection_event: asyncio.Event,
                 extraction_done_event: asyncio.Event,
                 order_count_ref: dict):
        super().__init__(session, stop_event, name="ManiaExtract")
        self._monitor = monitor
        self._detection_event = detection_event
        self._extraction_done_event = extraction_done_event
        self._order_count_ref = order_count_ref

    async def run(self):
        await self._navigate(SELL_ING_URL, "提取页(预加载)")
        await self._wait_page_stable()
        print(f"[{self._log_tag}] 提取就绪，等待检测信号")

        while not self.stopped:
            self._touch()
            try:
                await asyncio.wait_for(
                    self._detection_event.wait(), timeout=1)
            except asyncio.TimeoutError:
                continue

            count = self._order_count_ref.get('count', 0)
            print(f"[{self._log_tag}] 收到信号 (count={count})，开始提取")

            try:
                await self._navigate(SELL_ING_URL, "提取订单")
                await self._wait_page_stable()
                reported = await self._monitor._collect_and_report_orders(
                    self.page)
                print(f"[{self._log_tag}] 上报 {reported} 个订单")
            except Exception as e:
                print(f"[{self._log_tag}] 提取异常: {e}")
            finally:
                self._detection_event.clear()
                self._extraction_done_event.set()


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
        await self._navigate(SELL_REGIST_URL, "刷新-回到上架页")

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
                                         wait_until="domcontentloaded",
                                         timeout=timeout)
                    await self.page.wait_for_timeout(1000)
                    try:
                        await self.page.wait_for_load_state(
                            "networkidle", timeout=15000)
                    except Exception:
                        pass
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
                try:
                    await self.page.wait_for_load_state(
                        "networkidle", timeout=10000)
                except Exception:
                    pass
            else:
                print(f"[{self._log_tag}] 未找到 reregist 按钮")
        else:
            print(f"[{self._log_tag}] 无可刷新的商品")


class ItemmaniaMonitor(BaseOrderMonitor):
    """ItemMania 站点订单监控（Async 多页面并行）。"""

    tag = "mania"
    skip_login = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._detection_event = asyncio.Event()
        self._extraction_done_event = asyncio.Event()
        self._order_count_ref = {'count': 0}

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
            ManiaDetectionWorker(
                self._session, self.stop_event, self,
                self._detection_event, self._extraction_done_event,
                self._order_count_ref,
            ),
            ManiaExtractionWorker(
                self._session, self.stop_event, self,
                self._detection_event, self._extraction_done_event,
                self._order_count_ref,
            ),
            ManiaRefreshWorker(
                self._session, self.stop_event, self,
            ),
        ]

    def _is_target_page(self, url: str) -> bool:
        return SELL_REGIST_URL in url or SELL_ING_URL in url

    def _is_on_collect_page(self, page) -> bool:
        return "sell_ing" in page.url

    async def _extract_orders_from_table(self, page) -> list:
        """从 sell_ing.html 表格提取所有订单数据。"""
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

                game_el = tds.nth(0).locator('strong')
                game_name = (
                    (await game_el.inner_text()).strip()
                    if await game_el.count() > 0 else ''
                )
                server_el = tds.nth(0).locator('p')
                server = (
                    (await server_el.inner_text()).strip()
                    if await server_el.count() > 0 else ''
                )

                item_type = (await tds.nth(1).inner_text()).strip()

                link_el = tds.nth(2).locator('a')
                trade_id = ''
                if await link_el.count() > 0:
                    href = await link_el.get_attribute('href') or ''
                    m = re.search(r'id=(\d+)', href)
                    if m:
                        trade_id = m.group(1)

                qty_el = tds.nth(2).locator('.sub_trade_title')
                quantity = (
                    (await qty_el.inner_text()).strip()
                    if await qty_el.count() > 0 else ''
                )

                title_el = tds.nth(2).locator('.trade_title')
                title = (
                    (await title_el.inner_text()).strip()
                    if await title_el.count() > 0 else ''
                )

                price_text = (await tds.nth(3).inner_text()).strip()
                time_text = (await tds.nth(4).inner_text()).strip()

                status_el = tds.nth(5).locator('.btn_base, span').first
                status = (
                    (await status_el.inner_text()).strip()
                    if await status_el.count() > 0 else ''
                )

                orders.append({
                    'game_name': game_name, 'server': server,
                    'item_type': item_type, 'order_no': trade_id,
                    'quantity': quantity, 'product_title': title,
                    'price': price_text, 'order_time': time_text,
                    'state': STATUS_MAP.get(status, status),
                })
            except Exception as e:
                print(f"[{self._log_tag}] 行 #{i} 提取失败: {e}")
                continue

        return orders

    async def _build_normalized_order(self, page, order_data: dict):
        """通过 ItemmaniaAdapter 标准化订单（异步提取买家信息）。"""
        trade_id = order_data.get('order_no', '')
        buyer = ''
        platform_order_time = order_data.get('order_time', '')

        # 尝试从详情页提取买家信息
        if self._session and trade_id:
            buyer, platform_order_time = await self._fetch_buyer_detail(trade_id)

        # 买家 fallback（adapter 要求非空）
        if not buyer:
            buyer = f"buyer-{trade_id}"
        order_data['buyer_name'] = buyer

        # 价格解析
        price_text = order_data.get('price', '0')
        try:
            platform_price = parse_korean_amount(
                price_text.replace('원', ''))
        except ValueError:
            platform_price = Decimal('0')

        # 通过适配器一次性构建 NormalizedOrder
        adapter = adapter_for("itemmania")
        normalized = adapter.normalize(
            order_data,
            platform_order_time=platform_order_time,
            platform_price=platform_price,
            platform_item_type=order_data.get('item_type', ''),
        )
        if normalized is None:
            print(f"[{self._log_tag}] 适配器拒绝订单 "
                  f"(trade_id={trade_id}): {adapter.last_reject_reason}")
            return None

        print(f"[{self._log_tag}] 订单已上报: "
              f"trade_id={trade_id}, "
              f"price={price_text}, "
              f"buyer={buyer[:10]}...")
        return normalized

    async def _fetch_buyer_detail(self, trade_id: str) -> tuple:
        """异步打开详情页提取买家角色名和平台订单时间。"""
        detail_url = f"{SELL_ING_VIEW_URL}?id={trade_id}&type=sell"
        detail_page = None
        try:
            detail_page = await self._session.new_page()
            await detail_page.goto(detail_url, wait_until="domcontentloaded",
                                   timeout=15000)
            await detail_page.wait_for_timeout(2000)
            try:
                await detail_page.wait_for_load_state("networkidle",
                                                       timeout=10000)
            except Exception:
                pass

            buyer = ''
            try:
                buyer_el = detail_page.locator('span.f_black.f_20').first
                if await buyer_el.count() > 0:
                    buyer = (await buyer_el.inner_text()).strip()
            except Exception:
                pass

            if not buyer:
                try:
                    result = await detail_page.evaluate("""
                        async () => {
                            const lis = document.querySelectorAll('li');
                            for (const li of lis) {
                                const text = li.textContent || '';
                                const m = text.match(/구매자\\s*캐릭터명\\s*:\\s*(.+)/);
                                if (m) return m[1].trim();
                            }
                            return '';
                        }
                    """)
                    buyer = (result or "").strip()
                except Exception:
                    pass

            platform_order_time = ''
            try:
                time_el = detail_page.locator('.trade_category span').first
                if await time_el.count() > 0:
                    platform_order_time = (await time_el.inner_text()).strip()
            except Exception:
                pass

            return (buyer, platform_order_time)
        except Exception as e:
            print(f"[{self._log_tag}] 详情页提取失败 "
                  f"(trade_id={trade_id}): {e}")
            return ('', '')
        finally:
            if detail_page:
                try:
                    await detail_page.close()
                except Exception:
                    pass
