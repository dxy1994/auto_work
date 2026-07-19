"""
ItemBay 订单监控子类（Async 多页面并行架构）。

特性：
  - 通过 #New3 图标检测新订单
  - 上架刷新：导航到上架管理 → 查找非活跃商品 → 点击重新上架

Worker 分工：
  - ItembayDetectionWorker：固定在售品列表页，轮询 #New3 图标
  - ItembayRefreshWorker：定期导航到上架管理页刷新商品
"""
import asyncio
import datetime
from typing import List, Tuple

from monitor.monitoring.base import BaseOrderMonitor
from monitor.monitoring.worker import PageWorker
from monitor.browser.audio import play_alert_audio_async


SELL_LIST_URL = (
    "https://www.itembay.com/mybay/status/mybayStatusSellList"
)


class ItembayDetectionWorker(PageWorker):
    """ItemBay 订单检测 Worker。"""

    def __init__(self, session, stop_event, monitor: 'ItembayMonitor'):
        super().__init__(session, stop_event, name="ItembayDetect")
        self._monitor = monitor

    async def run(self):
        cfg = self._monitor.get_order_cfg()
        my_page_url = cfg.get("my_page_url", SELL_LIST_URL)
        wait_timeout = cfg.get("wait_timeout", 10000)
        refresh_interval = cfg.get("refresh_interval", 3)

        await self._navigate(my_page_url, "检测页")
        await self._wait_page_stable()

        print(f"[{self._log_tag}] 检测循环开始 (interval={refresh_interval}s)")
        check_round = 0

        while not self.stopped:
            await self._session.chat_sender_pause.wait()
            check_round += 1
            self._touch()
            try:
                detected, count, alert_text = await self._detect()
                if detected:
                    print(f"[{self._log_tag}] "
                          f"第{check_round}轮: {alert_text}")
                    tag = self._monitor.tag
                    acct = self._monitor.account_id
                    await play_alert_audio_async(
                        text=f"{tag}账号{acct}: {alert_text}")
                elif check_round % 10 == 1:
                    print(f"[{self._log_tag}] 第{check_round}轮: 无订单")
            except Exception as e:
                print(f"[{self._log_tag}] 第{check_round}轮异常: {e}")
                if not self.stopped:
                    await self._safe_reload_or_navigate(my_page_url,
                                                        wait_timeout)

            await asyncio.sleep(refresh_interval)

    async def _detect(self) -> Tuple[bool, int, str]:
        """通过 #New3 图标检测新订单。"""
        try:
            await self.page.wait_for_selector("#New3", state="attached",
                                              timeout=5000)
        except Exception:
            return (False, 0, "")
        img = await self.page.query_selector("#New3 img")
        has_order = img is not None
        if has_order:
            print(f"[{self._log_tag}] 检测到订单: #New3 图标存在")
        return (has_order, 1 if has_order else 0,
                "检测到订单！" if has_order else "")


class ItembayRefreshWorker(PageWorker):
    """ItemBay 商品刷新 Worker。"""

    def __init__(self, session, stop_event, monitor: 'ItembayMonitor'):
        super().__init__(session, stop_event, name="ItembayRefresh")
        self._monitor = monitor
        self._last_refresh = datetime.datetime.now()

    async def run(self):
        cfg = self._monitor.get_order_cfg()
        wait_timeout = cfg.get("wait_timeout", 10000)
        interval = 40

        await self._navigate(SELL_LIST_URL, "刷新页")
        await self._wait_page_stable()
        print(f"[{self._log_tag}] 刷新就绪 (间隔={interval}s)")

        while not self.stopped:
            await self._session.chat_sender_pause.wait()
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
        """导航到上架管理 → 查找可刷新商品 → 重新上架。"""
        try:
            await self.page.wait_for_selector("#NavigationPanel",
                                              timeout=1000)
        except Exception:
            print(f"[{self._log_tag}] NavigationPanel 未找到")
            await self._find_and_refresh(timeout)
            return

        third = await self.page.query_selector(
            "#NavigationPanel > :nth-child(3)")
        if third:
            tn = await third.evaluate("el => el.tagName.toLowerCase()")
            if tn == "a":
                href = await third.get_attribute("href")
                if href:
                    print(f"[{self._log_tag}] 跳转上架页面: {href}")
                    try:
                        await self.page.goto(href,
                                             wait_until="domcontentloaded",
                                             timeout=timeout)
                    except Exception as e:
                        print(f"[{self._log_tag}] 跳转超时: {e}")
                    await self.page.wait_for_timeout(1000)
                    try:
                        await self.page.wait_for_load_state(
                            "networkidle", timeout=5000)
                    except Exception:
                        pass
            else:
                print(f"[{self._log_tag}] 第3元素非链接(tag={tn})")
        else:
            print(f"[{self._log_tag}] NavigationPanel 无第3子元素")

        await self._find_and_refresh(timeout)

    async def _find_and_refresh(self, timeout: int):
        """在列表页查找可刷新的商品并点击重新上架。"""
        try:
            await self.page.wait_for_selector(
                "#frmMybay .list_type tbody tr", timeout=2000)
        except Exception:
            pass

        trs = await self.page.query_selector_all(
            "#frmMybay .list_type tbody tr")
        print(f"[{self._log_tag}] 商品数量: {len(trs)}")

        target_tr = None
        for tr in trs:
            cls = await tr.get_attribute("class") or ""
            if "bg_01" not in cls:
                target_tr = tr

        if not target_tr:
            redirect_url = None
            first = await self.page.query_selector(
                "#NavigationPanel > :nth-child(1)")
            if first:
                tn = await first.evaluate(
                    "el => el.tagName.toLowerCase()")
                if tn == "a":
                    href = await first.get_attribute("href")
                    if href:
                        redirect_url = href
                        print(f"[{self._log_tag}] 跳转NavPanel第1个: {href}")
            if not redirect_url:
                redirect_url = (
                    "https://www.itembay.com/mybay/status/"
                    "mybayStatusSellList?ItemSeq=1&tiDirection=0"
                )
                print(f"[{self._log_tag}] 跳转固定地址: {redirect_url}")
            try:
                await self.page.goto(redirect_url,
                                     wait_until="domcontentloaded",
                                     timeout=timeout)
            except Exception as e:
                print(f"[{self._log_tag}] 跳转超时: {e}")
            await self.page.wait_for_timeout(1000)
            try:
                await self.page.wait_for_load_state("networkidle",
                                                    timeout=5000)
            except Exception:
                pass

            try:
                await self.page.wait_for_selector(
                    "#frmMybay .list_type tbody tr", timeout=2000)
            except Exception:
                pass
            trs = await self.page.query_selector_all(
                "#frmMybay .list_type tbody tr")
            print(f"[{self._log_tag}] 跳转后商品: {len(trs)}")
            for tr in trs:
                cls = await tr.get_attribute("class") or ""
                if "bg_01" not in cls:
                    target_tr = tr
                    break

        if target_tr:
            btn = await target_tr.query_selector(".btn_pop01.type03")
            if btn:
                await btn.click()
                await self.page.wait_for_timeout(2000)
                try:
                    await self.page.wait_for_load_state(
                        "networkidle", timeout=10000)
                except Exception:
                    pass
                try:
                    await self.page.wait_for_selector(
                        "#imgSubmitButton", timeout=8000)
                    await self.page.wait_for_timeout(500)
                    submit = await self.page.query_selector(
                        "#imgSubmitButton")
                    if submit:
                        print(f"[{self._log_tag}] 点击确认按钮")
                        await submit.click()
                        await self.page.wait_for_timeout(2000)
                        try:
                            await self.page.wait_for_load_state(
                                "networkidle", timeout=10000)
                        except Exception:
                            pass
                except Exception as e:
                    print(f"[{self._log_tag}] 确认按钮异常: {e}")
            else:
                print(f"[{self._log_tag}] 未找到刷新按钮")
        else:
            print(f"[{self._log_tag}] 无可刷新的商品")


class ItembayMonitor(BaseOrderMonitor):
    """ItemBay 站点订单监控。"""

    tag = "itemBay"

    def get_order_cfg(self) -> dict:
        return {
            "my_page_url": SELL_LIST_URL,
            "my_page_selector": "",
            "wait_timeout": 10000,
            "refresh_interval": 3,
            "max_retries": 999,
        }

    def _get_workers(self) -> List[PageWorker]:
        return [
            ItembayDetectionWorker(self._session, self.stop_event, self),
            ItembayRefreshWorker(self._session, self.stop_event, self),
        ]

    def _is_target_page(self, url: str) -> bool:
        return "itembay.com/mybay" in url
