"""
PageWorker — 页面级独立任务基类（Async API）。

每个 PageWorker：
  - 拥有独立的 Page（标签页），导航互不干扰
  - 通过 BrowserSession 共享 Cookie / Storage
  - async run() 方法由子类覆写，作为 asyncio Task 并发执行
  - 可通过 session.new_page() 动态创建子页面
"""

import asyncio
import threading
import time
from abc import ABC, abstractmethod
from typing import Optional

from patchright.async_api import Page

from automation.browser_session import BrowserSession


class PageWorker(ABC):
    """页面级独立任务基类（Async）。"""

    def __init__(
        self,
        session: BrowserSession,
        stop_event: Optional[threading.Event],
        name: str = "",
    ):
        self._session = session
        self._stop_event = stop_event
        self._name = name or self.__class__.__name__
        self._page: Optional[Page] = None  # 延迟创建（在 run() 中）
        self._last_active_ts: float = time.time()  # 心跳时间戳

    # ── 属性 ──

    @property
    def page(self) -> Page:
        """当前 Worker 绑定的页面。在 run() 首次访问时自动创建。"""
        if self._page is None:
            raise RuntimeError(
                "Page 尚未初始化，请在 async run() 中调用 await self.init_page()")
        return self._page

    @property
    def session(self) -> BrowserSession:
        """共享的浏览器会话。"""
        return self._session

    @property
    def stopped(self) -> bool:
        """检查是否收到终止信号。"""
        return (self._stop_event is not None
                and self._stop_event.is_set())

    @property
    def _log_tag(self) -> str:
        """日志前缀。"""
        return f"{self._name}:{self._session.account_id}"

    # ── 心跳 ──

    @property
    def last_active(self) -> float:
        """上次活跃时间戳。"""
        return self._last_active_ts

    def _touch(self):
        """更新心跳时间戳（Worker 应在每次循环迭代时调用）。"""
        self._last_active_ts = time.time()

    # ── 初始化 ──

    async def init_page(self):
        """从 session 认领一个页面（优先复用已有页面）。必须在 run() 中调用。"""
        if self._page is None:
            self._page = await self._session.claim_page()
            print(f"[{self._log_tag}] PageWorker 已认领页面, "
                  f"url={self._page.url}")

    # ── 钩子 ──

    @abstractmethod
    async def run(self):
        """子类覆写：实现具体任务循环（async）。"""
        ...

    async def on_stop(self):
        """子类可选覆写：收到终止信号时的清理逻辑。"""
        pass

    # ── 动态页面 ──

    async def spawn_page(self) -> Page:
        """从共享 Session 创建新的子页面（用于临时任务，如订单详情提取）。"""
        return await self._session.new_page()

    # ── 页面辅助 ──

    async def _wait_page_stable(self, timeout: int = 15000):
        """等待页面稳定。"""
        await self._page.wait_for_timeout(1000)
        try:
            await self._page.wait_for_load_state("networkidle",
                                                 timeout=timeout)
        except Exception:
            pass

    async def _navigate(self, url: str, reason: str = "",
                        timeout: int = 15000,
                        wait_until: str = "domcontentloaded",
                        skip_networkidle: bool = False):
        """导航到指定 URL，带日志。"""
        if url not in self._page.url:
            log_reason = f" ({reason})" if reason else ""
            print(f"[{self._log_tag}] 导航到{log_reason}: {url}")
            await self._page.goto(url, wait_until=wait_until,
                                  timeout=timeout)
            await self._page.wait_for_timeout(1000)
            if not skip_networkidle:
                try:
                    await self._page.wait_for_load_state("networkidle",
                                                         timeout=timeout)
                except Exception:
                    pass

    async def _safe_reload_or_navigate(self, my_page_url: str,
                                       wait_timeout: int = 15000):
        """尝试刷新页面，失败则重新导航。"""
        try:
            await self._page.reload(wait_until="domcontentloaded",
                                    timeout=wait_timeout)
        except Exception as e:
            print(f"[{self._log_tag}] 刷新超时: {e}，重新导航")
            await self._page.goto(my_page_url,
                                  wait_until="domcontentloaded",
                                  timeout=wait_timeout)
            await self._page.wait_for_timeout(2000)

    async def stop(self):
        """安全停止当前 Worker 页面操作。"""
        await self.on_stop()
        if self._page:
            try:
                if not self._page.is_closed():
                    await self._page.close()
            except Exception:
                pass
        print(f"[{self._log_tag}] PageWorker 已停止")
