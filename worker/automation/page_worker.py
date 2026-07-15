"""
PageWorker — 页面级独立任务基类。

每个 PageWorker：
  - 拥有独立的 Page（标签页），导航互不干扰
  - 通过 BrowserSession 共享 Cookie / Storage
  - run() 方法由子类覆写，实现具体循环逻辑
  - 可通过 session.new_page() 动态创建子页面
"""

import threading
from abc import ABC, abstractmethod
from typing import Optional

from patchright.sync_api import Page

from automation.browser_session import BrowserSession


class PageWorker(ABC):
    """页面级独立任务基类。"""

    def __init__(
        self,
        session: BrowserSession,
        stop_event: threading.Event,
        name: str = "",
    ):
        self._session = session
        self._stop_event = stop_event
        self._name = name or self.__class__.__name__

        # 创建独立页面
        self._page = session.new_page()
        print(f"[{self._log_tag}] PageWorker 已创建, page_url={self._page.url}")

    # ── 属性 ──

    @property
    def page(self) -> Page:
        """当前 Worker 绑定的页面。"""
        return self._page

    @property
    def session(self) -> BrowserSession:
        """共享的浏览器会话。"""
        return self._session

    @property
    def stopped(self) -> bool:
        """检查是否收到终止信号。"""
        return self._stop_event.is_set()

    @property
    def _log_tag(self) -> str:
        """日志前缀。"""
        return f"{self._name}:{self._session.account_id}"

    # ── 钩子 ──

    @abstractmethod
    def run(self):
        """子类覆写：实现具体任务循环。"""
        ...

    def on_stop(self):
        """子类可选覆写：收到终止信号时的清理逻辑。"""
        pass

    # ── 动态页面 ──

    def spawn_page(self) -> Page:
        """从共享 Session 创建新的子页面（用于临时任务，如订单详情提取）。"""
        return self._session.new_page()

    # ── 页面辅助 ──

    def _wait_page_stable(self, timeout: int = 15000):
        """等待页面稳定。"""
        self._page.wait_for_timeout(1000)
        try:
            self._page.wait_for_load_state("networkidle", timeout=timeout)
        except Exception:
            pass

    def _navigate(self, url: str, reason: str = "",
                  timeout: int = 15000, wait_until: str = "domcontentloaded"):
        """导航到指定 URL，带日志。"""
        if url not in self._page.url:
            log_reason = f" ({reason})" if reason else ""
            print(f"[{self._log_tag}] 导航到{log_reason}: {url}")
            self._page.goto(url, wait_until=wait_until, timeout=timeout)
            self._page.wait_for_timeout(1000)
            try:
                self._page.wait_for_load_state("networkidle", timeout=timeout)
            except Exception:
                pass

    def _safe_reload_or_navigate(self, my_page_url: str,
                                 wait_timeout: int = 15000):
        """尝试刷新页面，失败则重新导航。"""
        try:
            self._page.reload(wait_until="domcontentloaded",
                              timeout=wait_timeout)
        except Exception as e:
            print(f"[{self._log_tag}] 刷新超时: {e}，重新导航")
            self._page.goto(my_page_url, wait_until="domcontentloaded",
                            timeout=wait_timeout)
            self._page.wait_for_timeout(2000)

    def stop(self):
        """安全停止当前 Worker 页面操作。"""
        self.on_stop()
        try:
            if self._page and not self._page.is_closed():
                self._page.close()
        except Exception:
            pass
        print(f"[{self._log_tag}] PageWorker 已停止")
