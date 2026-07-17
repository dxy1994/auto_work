"""
Barotem 订单监控子类（Async 多页面并行架构）。

特性：
  - 通过侧栏 DOM 检测订单数量
  - 登录后弹窗检测
  - 单 Worker 模式
"""
import asyncio
import re
from typing import List, Tuple

from monitoring.base import BaseOrderMonitor
from monitoring.worker import PageWorker
from browser.audio import play_alert_audio_async


class BarotemDetectionWorker(PageWorker):
    """Barotem 订单检测 Worker。"""

    def __init__(self, session, stop_event, monitor: 'BarotemMonitor'):
        super().__init__(session, stop_event, name="BarotemDetect")
        self._monitor = monitor

    async def run(self):
        cfg = self._monitor.get_order_cfg()
        my_page_url = cfg.get("my_page_url", "https://www.barotem.com/mypage")
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
                need_relogin = await self._monitor.post_login_check(self.page)
                if need_relogin:
                    print(f"[{self._log_tag}] 检测到登录弹窗，复用 _do_login 重新登录")
                    lr = await self._session._do_login()
                    if lr["status"] != "success":
                        raise Exception(f"重新登录失败: {lr['message']}")
                    await self._navigate(my_page_url, "重登录后返回")
                    await self._wait_page_stable()
                    continue

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
        """通过侧栏计数徽章检测订单。"""
        sel = ("body > main > div.mypage_container > nav > div > "
               "ul:nth-child(1) > li:nth-child(2) > a > span")
        try:
            await self.page.wait_for_selector(sel, timeout=10000)
        except Exception:
            return (False, 0, "")
        text = await self.page.text_content(sel) or "0"
        nums = re.findall(r'\d+', text)
        count = int(nums[0]) if nums else 0
        if count > 0:
            print(f"[{self._log_tag}] 检测到订单: count={count}")
        return (count > 0, count, f"检测到 {count} 个订单！")


class BarotemMonitor(BaseOrderMonitor):
    """Barotem 站点订单监控。"""

    tag = "arotem"

    def get_order_cfg(self) -> dict:
        return {
            "my_page_url": "https://www.barotem.com/mypage",
            "my_page_selector": "",
            "wait_timeout": 10000,
            "refresh_interval": 3,
            "max_retries": 999,
        }

    def _get_workers(self) -> List[PageWorker]:
        return [
            BarotemDetectionWorker(self._session, self.stop_event, self),
        ]

    def _is_target_page(self, url: str) -> bool:
        return "barotem.com/mypage" in url

    async def post_login_check(self, page) -> bool:
        """检测登录提示弹窗。"""
        try:
            alert_el = await page.query_selector("div.common_alert_check")
            if alert_el:
                onclick = await alert_el.get_attribute("onclick") or ""
                if "/auth/login" in onclick:
                    print(f"[{self._log_tag}] 检测到登录弹窗，需重新登录")
                    return True
                else:
                    print(f"[{self._log_tag}] 弹窗为非登录提示，忽略")
        except Exception:
            pass
        return False
