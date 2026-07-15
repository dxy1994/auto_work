"""
ItemMania 订单监控子类（多页面并行架构）。

Worker 分工：
  - DetectionWorker：固定在 sell_regist.html，AJAX 轮询订单数，有订单时通知提取
  - ExtractionWorker：收到信号后导航到 sell_ing.html，提取订单并上报总控
  - RefreshWorker：固定在 sell_regist.html 末页，定时点击「재등록」刷新上架

共享通信：
  - detection_event: 检测到订单时 set
  - extraction_done_event: 提取完成后 set，通知检测恢复轮询
  - order_count: 当前检测到的订单数（线程安全）
"""

import datetime
import re
import threading
import time
from decimal import Decimal
from typing import Optional, Tuple, List

from patchright.sync_api import Page

from automation.order_monitor import BaseOrderMonitor
from automation.page_worker import PageWorker
from automation.audio_alert import play_alert_audio
from orders.adapters import parse_korean_amount
from orders.model import NormalizedOrder

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


# ═══════════════════════════════════════════════════════════
# PageWorker 子类
# ═══════════════════════════════════════════════════════════

class ManiaDetectionWorker(PageWorker):
    """订单检测 Worker：AJAX 轮询订单数，有订单时通知 ExtractionWorker。"""

    def __init__(self, session, stop_event, monitor: 'ItemmaniaMonitor',
                 detection_event: threading.Event,
                 extraction_done_event: threading.Event,
                 order_count_ref: dict):
        super().__init__(session, stop_event, name="ManiaDetect")
        self._monitor = monitor
        self._detection_event = detection_event
        self._extraction_done_event = extraction_done_event
        self._order_count_ref = order_count_ref
        self._lock = threading.Lock()

    def run(self):
        refresh_interval = self._monitor.get_order_cfg().get("refresh_interval", 3)
        wait_timeout = self._monitor.get_order_cfg().get("wait_timeout", 10000)

        # 导航到 sell_regist.html
        self._navigate(SELL_REGIST_URL, "检测页")
        self._wait_page_stable()

        print(f"[{self._log_tag}] 订单检测循环开始 "
              f"(interval={refresh_interval}s)")

        check_round = 0
        while not self.stopped:
            check_round += 1

            try:
                count = self._ajax_detect()
                if count is None:
                    # AJAX 检测失败，刷新页面重试
                    if check_round % 10 == 1:
                        print(f"[{self._log_tag}] "
                              f"第{check_round}轮: AJAX检测失败，刷新")
                    self._safe_reload_or_navigate(SELL_REGIST_URL,
                                                  wait_timeout)
                    time.sleep(refresh_interval)
                    continue

                if count > 0:
                    with self._lock:
                        self._order_count_ref['count'] = count

                    print(f"[{self._log_tag}] 第{check_round}轮: "
                          f"检测到 {count} 个订单！")
                    tag = self._monitor.tag
                    acct = self._monitor.account_id
                    play_alert_audio(
                        text=f"{tag}账号{acct}: 检测到 {count} 个订单！")

                    # 通知 ExtractionWorker
                    self._extraction_done_event.clear()
                    self._detection_event.set()

                    # 等待提取完成
                    print(f"[{self._log_tag}] 等待订单提取完成...")
                    while not self.stopped:
                        if self._extraction_done_event.wait(timeout=1):
                            break
                    print(f"[{self._log_tag}] 订单提取完成，恢复检测")

                    # 等待提取完成后再刷新页面（提取过程中页面可能被导航）
                    self._safe_reload_or_navigate(SELL_REGIST_URL,
                                                  wait_timeout)
                else:
                    if check_round % 10 == 1:
                        print(f"[{self._log_tag}] "
                              f"第{check_round}轮: 无订单，"
                              f"{refresh_interval}s后刷新")

            except Exception as e:
                print(f"[{self._log_tag}] 第{check_round}轮检测异常: {e}")

            # 等待 + 刷新
            time.sleep(refresh_interval)
            if not self.stopped:
                self._safe_reload_or_navigate(SELL_REGIST_URL,
                                              wait_timeout)

    def _ajax_detect(self) -> Optional[int]:
        """调用 AJAX 计数接口，返回在售订单数。失败返回 None。"""
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
            result = self.page.evaluate(js)
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
    """订单提取 Worker：收到信号后导航到 sell_ing.html，提取并上报订单。"""

    def __init__(self, session, stop_event, monitor: 'ItemmaniaMonitor',
                 detection_event: threading.Event,
                 extraction_done_event: threading.Event,
                 order_count_ref: dict):
        super().__init__(session, stop_event, name="ManiaExtract")
        self._monitor = monitor
        self._detection_event = detection_event
        self._extraction_done_event = extraction_done_event
        self._order_count_ref = order_count_ref

    def run(self):
        wait_timeout = self._monitor.get_order_cfg().get("wait_timeout", 10000)

        # 先导航到 sell_ing.html（提前加载，收到信号后直接提取）
        self._navigate(SELL_ING_URL, "提取页(预加载)")
        self._wait_page_stable()

        print(f"[{self._log_tag}] 订单提取就绪，等待检测信号")

        while not self.stopped:
            # 等待检测信号
            if not self._detection_event.wait(timeout=1):
                continue

            # 收到信号，执行提取
            count = self._order_count_ref.get('count', 0)
            print(f"[{self._log_tag}] 收到检测信号 (count={count})，开始提取")

            try:
                # 确保在 sell_ing.html
                self._navigate(SELL_ING_URL, "提取订单")
                self._wait_page_stable()

                # 委托 Monitor 的模板方法完成提取+上报
                reported = self._monitor._collect_and_report_orders(self.page)
                print(f"[{self._log_tag}] 本次上报 {reported} 个订单")

            except Exception as e:
                print(f"[{self._log_tag}] 订单提取异常: {e}")
            finally:
                # 清除检测信号，通知 DetectionWorker 恢复
                self._detection_event.clear()
                self._extraction_done_event.set()


class ManiaRefreshWorker(PageWorker):
    """商品刷新 Worker：定时翻到末页点击「재등록」按钮。"""

    def __init__(self, session, stop_event, monitor: 'ItemmaniaMonitor'):
        super().__init__(session, stop_event, name="ManiaRefresh")
        self._monitor = monitor
        self._last_refresh = datetime.datetime.now()

    def run(self):
        wait_timeout = self._monitor.get_order_cfg().get("wait_timeout", 10000)
        interval = 40  # 刷新间隔（秒）

        # 导航到 sell_regist.html
        self._navigate(SELL_REGIST_URL, "刷新页")
        self._wait_page_stable()

        print(f"[{self._log_tag}] 商品刷新就绪 (间隔={interval}s)")

        while not self.stopped:
            elapsed = (datetime.datetime.now() -
                       self._last_refresh).total_seconds()
            if elapsed >= interval:
                try:
                    self._do_refresh(wait_timeout)
                    self._last_refresh = datetime.datetime.now()
                except Exception as e:
                    print(f"[{self._log_tag}] 刷新异常: {e}")

            time.sleep(5)  # 每 5 秒检查一次

    def _do_refresh(self, timeout: int):
        """翻到最后一页 → 点击最旧商品的「재등록」按钮。"""
        # 确保在 sell_regist.html
        self._navigate(SELL_REGIST_URL, "刷新-回到上架页")

        # 1. 翻到最后一页
        try:
            self.page.wait_for_selector(".cpnt.last", timeout=3000)
            last_link = self.page.query_selector(".cpnt.last a")
            if last_link:
                href = last_link.get_attribute("href")
                if href:
                    full_url = SELL_REGIST_URL + href
                    print(f"[{self._log_tag}] 跳转到末页: {full_url}")
                    self.page.goto(full_url,
                                   wait_until="domcontentloaded",
                                   timeout=timeout)
                    self.page.wait_for_timeout(1000)
                    try:
                        self.page.wait_for_load_state("networkidle",
                                                      timeout=15000)
                    except Exception:
                        pass
        except Exception:
            print(f"[{self._log_tag}] 无分页元素（仅1页），直接刷新当前页")

        # 2. 点击最后一行的「재등록」按钮
        try:
            self.page.wait_for_selector(".g_blue_table.tb_list tbody tr",
                                        timeout=3000)
        except Exception:
            pass
        trs = self.page.query_selector_all(".g_blue_table.tb_list tbody tr")
        print(f"[{self._log_tag}] 上架商品数量: {len(trs)}")
        if len(trs) >= 1:
            btn = trs[-1].query_selector(".flex_box .reregist")
            if btn:
                print(f"[{self._log_tag}] "
                      f"刷新上架: {trs[-1].text_content()[:60]}")
                btn.click()
                self.page.wait_for_timeout(2000)
                try:
                    self.page.wait_for_load_state("networkidle",
                                                  timeout=10000)
                except Exception:
                    pass
            else:
                print(f"[{self._log_tag}] 未找到 reregist 按钮")
        else:
            print(f"[{self._log_tag}] 无可刷新的上架商品")


# ═══════════════════════════════════════════════════════════
# ItemmaniaMonitor
# ═══════════════════════════════════════════════════════════

class ItemmaniaMonitor(BaseOrderMonitor):
    """ItemMania 站点订单监控（多页面并行）。"""

    tag = "mania"
    skip_login = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # ── Worker 间共享状态 ──
        self._detection_event = threading.Event()
        self._extraction_done_event = threading.Event()
        self._order_count_ref = {'count': 0}

    # ── 配置 ──

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

    # ── Worker 注册 ──

    def _get_workers(self) -> List[PageWorker]:
        """返回 3 个独立 PageWorker。"""
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

    # ── 页面校验（保留，供兼容）──

    def _is_target_page(self, url: str) -> bool:
        """目标页面为 sell_regist 或 sell_ing。"""
        return SELL_REGIST_URL in url or SELL_ING_URL in url

    # ── 订单检测（保留，供兼容旧调用）──

    def detect_order(self, page) -> Tuple[bool, int, str]:
        """旧版检测接口（多页面模式下不再使用）。"""
        return (False, 0, "")

    # ── 订单采集（供 ExtractionWorker 调用）──

    def _is_on_collect_page(self, page) -> bool:
        """仅当在 sell_ing.html 时才执行订单采集。"""
        return "sell_ing" in page.url

    def _extract_orders_from_table(self, page) -> list:
        """通过 Playwright 原生选择器从 sell_ing.html 表格提取所有订单数据。"""
        rows = page.locator('.g_blue_table.tb_list tbody tr')
        row_count = rows.count()
        orders = []

        for i in range(row_count):
            try:
                row = rows.nth(i)
                tds = row.locator('td')
                if tds.count() < 6:
                    continue

                # 跳过空态行
                if tds.nth(0).locator('.empty_item').count() > 0:
                    continue

                # td[0]: 游戏名 + 服务器
                game_el = tds.nth(0).locator('strong')
                game_name = (
                    game_el.inner_text().strip()
                    if game_el.count() > 0 else ''
                )
                server_el = tds.nth(0).locator('p')
                server = (
                    server_el.inner_text().strip()
                    if server_el.count() > 0 else ''
                )

                # td[1]: 物品类型
                item_type = tds.nth(1).inner_text().strip()

                # td[2]: 链接(href含trade_id) + 数量 + 标题
                link_el = tds.nth(2).locator('a')
                trade_id = ''
                if link_el.count() > 0:
                    href = link_el.get_attribute('href') or ''
                    m = re.search(r'id=(\d+)', href)
                    if m:
                        trade_id = m.group(1)

                qty_el = tds.nth(2).locator('.sub_trade_title')
                quantity = (
                    qty_el.inner_text().strip()
                    if qty_el.count() > 0 else ''
                )

                title_el = tds.nth(2).locator('.trade_title')
                title = (
                    title_el.inner_text().strip()
                    if title_el.count() > 0 else ''
                )

                # td[3]: 价格
                price_text = tds.nth(3).inner_text().strip()

                # td[4]: 时间
                time_text = tds.nth(4).inner_text().strip()

                # td[5]: 状态按钮
                status_el = tds.nth(5).locator('.btn_base, span').first
                status = (
                    status_el.inner_text().strip()
                    if status_el.count() > 0 else ''
                )

                orders.append({
                    'game_name': game_name,
                    'server': server,
                    'item_type': item_type,
                    'trade_id': trade_id,
                    'quantity': quantity,
                    'title': title,
                    'price': price_text,
                    'order_time': time_text,
                    'status': status,
                })
            except Exception as e:
                print(f"[{self._log_tag}] 行 #{i} 提取失败: {e}")
                continue

        return orders

    def _build_normalized_order(self, page, order_data: dict):
        """将 ItemMania 提取的原始数据转为 NormalizedOrder。"""
        trade_id = order_data.get('trade_id', '')
        context = page.context

        # 获取买家角色名 + 完整订单时间
        detail = self._fetch_order_detail(context, trade_id)
        buyer = detail.get('buyer', '')
        if not buyer:
            buyer = f"상세확인필요-{trade_id}"
            print(f"[{self._log_tag}] 无法获取买家名(trade_id={trade_id})，"
                  f"使用占位符")

        # 优先使用详情页的完整时间戳
        detail_time = detail.get('platform_order_time', '')
        platform_order_time = detail_time or order_data.get('order_time', '')

        # 映射韩文状态
        raw_status = order_data.get('status', '')
        mapped_status = STATUS_MAP.get(raw_status, raw_status)

        # 解析数量
        quantity_text = order_data.get('quantity', '')
        try:
            amount_value = parse_korean_amount(quantity_text)
        except ValueError:
            print(f"[{self._log_tag}] 无法解析数量: {quantity_text}")
            return None

        # 解析平台售价
        price_text = order_data.get('price', '0')
        try:
            platform_price = parse_korean_amount(
                price_text.replace('원', ''))
        except ValueError:
            platform_price = Decimal('0')

        normalized = NormalizedOrder(
            platform="itemmania",
            source_order_no=trade_id,
            region_external_key=order_data.get('server', ''),
            asset_type="adena",
            asset_amount=amount_value,
            buyer_character=buyer,
            platform_status=mapped_status,
            raw_title=order_data.get('title', ''),
            platform_order_time=platform_order_time,
            platform_price=platform_price,
            platform_item_type=order_data.get('item_type', ''),
        )

        print(f"[{self._log_tag}] 订单已上报: "
              f"trade_id={trade_id}, "
              f"price={order_data.get('price', 'N/A')}, "
              f"quantity={order_data.get('quantity', 'N/A')}, "
              f"buyer={buyer[:10]}...")
        return normalized

    def _fetch_order_detail(self, context, trade_id: str) -> dict:
        """打开订单详情页（新标签），提取买家角色名和完整订单时间。"""
        detail_url = f"{SELL_ING_VIEW_URL}?id={trade_id}&type=sell"
        detail_page = None
        result: dict = {'buyer': '', 'platform_order_time': ''}
        try:
            detail_page = context.new_page()
            detail_page.goto(detail_url, wait_until="domcontentloaded",
                             timeout=15000)
            detail_page.wait_for_timeout(2000)
            try:
                detail_page.wait_for_load_state("networkidle",
                                                timeout=10000)
            except Exception:
                pass

            # 1) 提取买家角色名
            try:
                char_el = detail_page.locator('span.f_black.f_20').first
                if char_el.count() > 0:
                    buyer = char_el.inner_text().strip()
                    if buyer:
                        result['buyer'] = buyer
                        print(f"[{self._log_tag}] 提取买家角色名: {buyer}")
            except Exception as e:
                print(f"[{self._log_tag}] Locator提取角色名失败: {e}")

            # 回退方案：JS 匹配
            if not result['buyer']:
                buyer = detail_page.evaluate("""
                () => {
                    const lis = document.querySelectorAll('li');
                    for (const li of lis) {
                        const text = li.textContent || '';
                        const m = text.match(
                            /구매자\\s*캐릭터명\\s*:\\s*(.+)/);
                        if (m) return m[1].trim();
                    }
                    return '';
                }
                """)
                result['buyer'] = (buyer or "").strip()
                if result['buyer']:
                    print(f"[{self._log_tag}] JS回退提取角色名: "
                          f"{result['buyer']}")

            # 2) 提取完整订单时间
            try:
                time_el = detail_page.locator('.trade_category span').first
                if time_el.count() > 0:
                    full_time = time_el.inner_text().strip()
                    if full_time:
                        result['platform_order_time'] = full_time
            except Exception as e:
                print(f"[{self._log_tag}] 提取完整时间失败: {e}")

            return result
        except Exception as e:
            print(f"[{self._log_tag}] 详情页提取失败 "
                  f"(trade_id={trade_id}): {e}")
            return result
        finally:
            if detail_page:
                try:
                    detail_page.close()
                except Exception:
                    pass
