"""
Barotem 订单监控子类（多页面并行架构）。

特性：
  - 通过侧栏 DOM 检测订单数量
  - 登录后弹窗检测：若检测到登录提示弹窗，触发强制重新登录
  - 单 Worker 模式（仅检测，无独立提取/刷新）

Worker：
  - BarotemDetectionWorker：固定在 mypage，轮询侧栏计数徽章
"""

import re
import threading
import time
from typing import Tuple, List

from automation.order_monitor import BaseOrderMonitor
from automation.page_worker import PageWorker
from automation.audio_alert import play_alert_audio


class BarotemDetectionWorker(PageWorker):
    """Barotem 订单检测 Worker：轮询侧栏计数徽章。"""

    def __init__(self, session, stop_event, monitor: 'BarotemMonitor'):
        super().__init__(session, stop_event, name="BarotemDetect")
        self._monitor = monitor

    def run(self):
        cfg = self._monitor.get_order_cfg()
        my_page_url = cfg.get("my_page_url", "https://www.barotem.com/mypage")
        wait_timeout = cfg.get("wait_timeout", 10000)
        refresh_interval = cfg.get("refresh_interval", 3)

        self._navigate(my_page_url, "检测页")
        self._wait_page_stable()

        print(f"[{self._log_tag}] 订单检测循环开始 "
              f"(interval={refresh_interval}s)")

        check_round = 0
        while not self.stopped:
            check_round += 1
            try:
                detected, count, alert_text = self._detect()
                if detected:
                    print(f"[{self._log_tag}] "
                          f"第{check_round}轮: {alert_text}")
                    tag = self._monitor.tag
                    acct = self._monitor.account_id
                    play_alert_audio(
                        text=f"{tag}账号{acct}: {alert_text}")
                elif check_round % 10 == 1:
                    print(f"[{self._log_tag}] 第{check_round}轮: 无订单，"
                          f"{refresh_interval}s后刷新")
            except Exception as e:
                print(f"[{self._log_tag}] 第{check_round}轮检测异常: {e}")

            time.sleep(refresh_interval)
            if not self.stopped:
                self._safe_reload_or_navigate(my_page_url, wait_timeout)

    def _detect(self) -> Tuple[bool, int, str]:
        """通过侧栏计数徽章检测订单。"""
        sel = ("body > main > div.mypage_container > nav > div > "
               "ul:nth-child(1) > li:nth-child(2) > a > span")
        try:
            self.page.wait_for_selector(sel, timeout=10000)
        except Exception:
            return (False, 0, "")
        text = self.page.text_content(sel) or "0"
        nums = re.findall(r'\d+', text)
        count = int(nums[0]) if nums else 0
        if count > 0:
            print(f"[{self._log_tag}] 检测到订单: count={count}")
        return (count > 0, count, f"检测到 {count} 个订单！")


class BarotemMonitor(BaseOrderMonitor):
    """Barotem 站点订单监控。"""

    tag = "arotem"

    # ── 配置 ──

    def get_order_cfg(self) -> dict:
        return {
            "my_page_url": "https://www.barotem.com/mypage",
            "my_page_selector": "",
            "wait_timeout": 10000,
            "refresh_interval": 3,
            "max_retries": 999,
        }

    # ── Worker 注册 ──

    def _get_workers(self) -> List[PageWorker]:
        return [
            BarotemDetectionWorker(self._session, self.stop_event, self),
        ]

    # ── 页面校验 ──

    def _is_target_page(self, url: str) -> bool:
        """目标页面为 barotem mypage。"""
        return "barotem.com/mypage" in url

    # ── 订单检测（保留兼容）──

    def detect_order(self, page) -> Tuple[bool, int, str]:
        return (False, 0, "")

    # ── 登录后检查 ──

    def post_login_check(self, page) -> bool:
        """检测登录提示弹窗，返回 True 表示需要重新登录。"""
        try:
            alert_el = page.query_selector("div.common_alert_check")
            if alert_el:
                onclick = alert_el.get_attribute("onclick") or ""
                if "/auth/login" in onclick:
                    print(f"[{self._log_tag}] 检测到登录弹窗，需重新登录")
                    return True
                else:
                    print(f"[{self._log_tag}] 弹窗为非登录提示，忽略")
        except Exception:
            pass
        return False
