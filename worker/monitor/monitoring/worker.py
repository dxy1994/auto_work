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

from monitor.browser.session import BrowserSession


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
        self._page: Optional[Page] = None
        self._page_crashed = False
        self._last_active_ts: float = time.time()

    @property
    def page(self) -> Page:
        if self._page is None:
            raise RuntimeError(
                "Page 尚未初始化，请在 async run() 中调用 await self.init_page()")
        return self._page

    @property
    def session(self) -> BrowserSession:
        return self._session

    @property
    def stopped(self) -> bool:
        return (self._stop_event is not None
                and self._stop_event.is_set())

    @property
    def _log_tag(self) -> str:
        return f"{self._name}:{self._session.account_id}"

    @property
    def last_active(self) -> float:
        return self._last_active_ts

    def _touch(self):
        self._last_active_ts = time.time()

    async def init_page(self):
        """从 session 认领一个页面（优先复用已有页面）。必须在 run() 中调用。"""
        if self._page is None:
            self._bind_page(await self._session.claim_page())
            print(f"[{self._log_tag}] PageWorker 已认领页面, "
                  f"url={self._page.url}")

    def _bind_page(self, page: Page):
        """绑定页面并监听 renderer crash；崩溃标签不一定会变成 closed。"""
        self._page = page
        self._page_crashed = False

        def _mark_crashed(*_args):
            if self._page is page:
                self._page_crashed = True
                print(
                    f"[{self._log_tag}] 检测到页面渲染进程崩溃，"
                    "将强制重建标签"
                )

        try:
            page.on("crash", _mark_crashed)
        except Exception:
            pass

    @abstractmethod
    async def run(self):
        """子类覆写：实现具体任务循环（async）。"""
        ...

    async def on_stop(self):
        """子类可选覆写：收到终止信号时的清理逻辑。"""
        pass

    async def spawn_page(self) -> Page:
        """从共享 Session 创建新的子页面（用于临时任务，如订单详情提取）。"""
        return await self._session.new_page()

    async def _wait_page_stable(self, timeout: int = 15000):
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
            self._session.release_page(self._page)
            try:
                if not self._page.is_closed():
                    await self._page.close()
            except Exception:
                pass
        print(f"[{self._log_tag}] PageWorker 已停止")

    async def recycle_page(self, reason: str) -> Page:
        """无条件换成新标签，用于崩溃恢复和长期页面的内存回收。"""
        old_page = self._page
        if old_page is None:
            await self.init_page()
            return self._page
        replacement = await self._session.replace_claimed_page(old_page)
        self._bind_page(replacement)
        self._touch()
        print(f"[{self._log_tag}] 已重建页面，原因：{reason}")
        return replacement

    def page_failure_requires_rebuild(self, error: Exception) -> bool:
        """识别 renderer crash；这类标签常保持打开状态但已无法执行脚本。"""
        if BrowserSession.is_driver_connection_error(error):
            self._session.mark_unhealthy(
                f"浏览器驱动连接已断开: {error}"
            )
            return True
        if self._page_crashed or self._page is None:
            return True
        try:
            if self._page.is_closed():
                return True
        except Exception:
            return True
        message = str(error).casefold()
        return any(marker in message for marker in (
            "page crashed",
            "target closed",
            "out of memory",
            "renderer",
            "has been closed",
        ))

    async def recover_page_after_failure(self, error: Exception) -> bool:
        """确认页面故障后强制更换标签，避免继续复用半崩溃 renderer。"""
        await self.recycle_page(f"Worker 异常: {error}")
        return True

    async def recover_closed_page(self) -> bool:
        """兼容旧调用：页面关闭或崩溃时换新标签。"""
        if (
            self._page is not None
            and not self._page_crashed
            and not self._page.is_closed()
        ):
            return False
        await self.recycle_page("页面已关闭或崩溃")
        print(f"[{self._log_tag}] 已自动重建异常关闭的 Worker 页面")
        return True
