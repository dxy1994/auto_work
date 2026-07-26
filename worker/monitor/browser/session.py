"""
BrowserSession — 按账户共享浏览器上下文，支持多页面并行（Async API）。

职责：
  - 同一 account_id 全局共享一个浏览器上下文（单例注册表）
  - 提供 new_page() 创建独立标签页
  - 启动时登录，运行中掉线后可重新登录，页面共享 Cookie / Storage
  - 生命周期管理：引用计数 → 最后关闭时上传配置到 RustFS
"""

import asyncio
import os
import sys
import threading
from typing import Optional, Dict

from patchright.async_api import async_playwright, Page, Browser, BrowserContext

from monitor import config
from monitor import storage as storage_sync
from common.runtime_paths import monitor_user_data_root

PLAYWRIGHT_HEADLESS = config.PLAYWRIGHT_HEADLESS

VIEWPORT = {"width": 1280, "height": 800}
_USER_DATA_ROOT = str(monitor_user_data_root())
_CHROMIUM_SANDBOX = sys.platform != "linux"

_CHROME_PATHS = [
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]

# ── 全局注册表 ──
_registry: Dict[int, 'BrowserSession'] = {}
_registry_lock = threading.Lock()


class BrowserSession:
    """一个账户一个浏览器上下文，多页面共享（Async API）。"""

    def __init__(
        self,
        account_id: int,
        login_url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        login_type: str = "form",
        login_config: Optional[dict] = None,
        skip_login: bool = False,
        force_login: bool = False,
        website_id: Optional[int] = None,
        my_page_url: str = "",
        stop_event: Optional[threading.Event] = None,
        headless: bool = False,
    ):
        self._account_id = account_id
        self._login_url = login_url
        self._username = username
        self._password = password
        self._login_type = login_type
        self._login_config = login_config or {}
        self._skip_login = skip_login
        self._force_login = force_login
        self._website_id = website_id
        self._my_page_url = my_page_url
        self._stop_event = stop_event
        self._headless = headless

        self._lock = threading.Lock()
        self._refcount = 0
        self._login_done = False
        self._login_result = None
        self._relogin_lock = asyncio.Lock()

        # 延迟初始化（在 async _init() 中完成）
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._main_page: Optional[Page] = None
        self._claimed_pages: set = set()
        self._transient_page_ids: set = set()
        self._transient_tasks: set = set()
        self._owner_loop: Optional[asyncio.AbstractEventLoop] = None
        self._closing = False

        # 公开属性：chat_sender 活跃时暂停检测的异步事件
        self.chat_sender_pause = asyncio.Event()
        self.chat_sender_pause.set()  # 默认不暂停

    # ── 公共属性 ──

    @property
    def account_id(self) -> int:
        return self._account_id

    def is_alive(self) -> bool:
        """浏览器与持久化上下文是否仍可使用。"""
        if self._context is None or self._playwright is None:
            return False
        try:
            if self._browser is not None and not self._browser.is_connected():
                return False
            self._context.pages
            return True
        except Exception:
            return False

    # ── 公共 API ──

    @classmethod
    def get_or_create(
        cls,
        account_id: int,
        login_url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        login_type: str = "form",
        login_config: Optional[dict] = None,
        skip_login: bool = False,
        force_login: bool = False,
        website_id: Optional[int] = None,
        my_page_url: str = "",
        stop_event: Optional[threading.Event] = None,
        headless: bool = False,
    ) -> 'BrowserSession':
        """获取或创建账户对应的 BrowserSession，同时递增引用计数。"""
        with _registry_lock:
            if account_id in _registry:
                session = _registry[account_id]
            else:
                session = cls(
                    account_id=account_id, login_url=login_url,
                    username=username, password=password,
                    login_type=login_type, login_config=login_config,
                    skip_login=skip_login, force_login=force_login,
                    website_id=website_id, my_page_url=my_page_url,
                    stop_event=stop_event, headless=headless,
                )
                _registry[account_id] = session
            session._add_ref()
            return session

    @classmethod
    def get_existing(cls, account_id: int) -> Optional['BrowserSession']:
        """只读获取已有会话，不改变引用计数。"""
        with _registry_lock:
            return _registry.get(account_id)

    @property
    def owner_loop(self) -> Optional[asyncio.AbstractEventLoop]:
        """返回创建 Playwright 的事件循环。"""
        return self._owner_loop

    async def init(self):
        """初始化浏览器（必须在 async 上下文中调用）。"""
        if self.is_alive():
            return
        if self._playwright is not None:
            await self.reset_after_crash()

        self._owner_loop = asyncio.get_running_loop()
        self._closing = False

        print(f"[BrowserSession:{self._account_id}] [1/5] 启动 playwright...", flush=True)
        self._playwright = await async_playwright().start()
        print(f"[BrowserSession:{self._account_id}] [2/5] playwright 已启动, 检测 channel...", flush=True)
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--restore-last-session",
        ]

        browser_type = None
        for ch in ("chrome", "msedge"):
            try:
                test = await self._playwright.chromium.launch(
                    channel=ch, headless=True,
                    args=["--headless"],
                    chromium_sandbox=_CHROMIUM_SANDBOX)
                await test.close()
                browser_type = ch
                print(f"[BrowserSession:{self._account_id}] channel={ch}")
                break
            except Exception:
                continue

        launch_kwargs: dict = {
            "headless": self._headless,
            "slow_mo": 300 if not self._headless else 0,
            "args": launch_args,
            "chromium_sandbox": _CHROMIUM_SANDBOX,
        }
        if browser_type:
            launch_kwargs["channel"] = browser_type
        else:
            for exe_path in _CHROME_PATHS:
                if os.path.isfile(exe_path):
                    launch_kwargs["executable_path"] = exe_path
                    print(f"[BrowserSession:{self._account_id}] "
                          f"exe={exe_path}")
                    break
            else:
                print(f"[BrowserSession:{self._account_id}] "
                      f"使用内置 Chromium")

        user_data_dir = os.path.join(_USER_DATA_ROOT,
                                     str(self._account_id))
        os.makedirs(user_data_dir, exist_ok=True)
        print(f"[BrowserSession:{self._account_id}] 持久化资料目录: {user_data_dir}")
        print(f"[BrowserSession:{self._account_id}] [3/5] 下载远程配置...", flush=True)
        storage_sync.download(self._account_id, user_data_dir)

        print(f"[BrowserSession:{self._account_id}] [4/5] 启动持久化上下文 (headless={self._headless})...", flush=True)
        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            viewport=VIEWPORT,
            timezone_id="Asia/Seoul",
            locale="ko-KR",
            **launch_kwargs,
        )
        self._browser = self._context.browser
        print(f"[BrowserSession:{self._account_id}] [5/5] 上下文已创建, 选取主页面...", flush=True)

        self._main_page = await self._pick_main_page()

        async def _safe_accept(dialog):
            try:
                await dialog.accept()
            except Exception:
                pass
        self._main_page.on("dialog", _safe_accept)

        print(f"[BrowserSession:{self._account_id}] 浏览器已启动, "
              f"main_page={self._main_page.url}")

    async def reset_after_crash(self):
        """丢弃已异常退出的运行时句柄，保留本地浏览器资料用于自动重启。"""
        if self.is_alive():
            return False
        current = asyncio.current_task()
        active_tasks = [
            task for task in self._transient_tasks
            if task is not current and not task.done()
        ]
        for task in active_tasks:
            task.cancel()
        if active_tasks:
            await asyncio.gather(*active_tasks, return_exceptions=True)
        try:
            if self._playwright is not None:
                await self._playwright.stop()
        except Exception:
            pass
        self._playwright = None
        self._browser = None
        self._context = None
        self._main_page = None
        self._claimed_pages.clear()
        self._transient_page_ids.clear()
        self._transient_tasks.clear()
        self._login_done = False
        self._login_result = None
        self._owner_loop = None
        self._closing = False
        print(f"[BrowserSession:{self._account_id}] 已清理异常会话，准备自动重启浏览器")
        return True

    async def _pick_main_page(self) -> Page:
        """从恢复的标签页中选健康页面作为主页面，保留其余健康旧标签。"""
        pages = self._context.pages
        if not pages:
            return await self._context.new_page()

        blanks = [p for p in pages if p.url == "about:blank"]
        non_blanks = [p for p in pages if p.url != "about:blank"]

        if non_blanks:
            keep = None
            for candidate in reversed(non_blanks):
                if await self._page_is_usable(candidate):
                    keep = candidate
                    break
                try:
                    await candidate.close()
                except Exception:
                    pass
            if keep is None:
                keep = blanks[0] if blanks else await self._context.new_page()
            to_close = [p for p in blanks if p != keep]
        elif blanks:
            keep = blanks[0]
            to_close = blanks[1:]
        else:
            return await self._context.new_page()

        for p in to_close:
            try:
                await p.close()
            except Exception:
                pass
        return keep

    async def claim_page(self) -> Page:
        """为 Worker 分配页面：复用健康旧标签，跳过临时页和崩溃页。"""
        context = self._context
        for p in list(context.pages):
            if (
                p == self._main_page
                or id(p) in self._claimed_pages
                or id(p) in self._transient_page_ids
            ):
                continue
            if not await self._page_is_usable(p):
                print(
                    f"[BrowserSession:{self._account_id}] "
                    f"关闭不可用的恢复页面 url={p.url}"
                )
                try:
                    await p.close()
                except Exception:
                    pass
                continue
            self._claimed_pages.add(id(p))
            print(f"[BrowserSession:{self._account_id}] 复用已有页面 url={p.url}")
            return p
        page = await self.new_page()
        self._claimed_pages.add(id(page))
        print(f"[BrowserSession:{self._account_id}] 新建页面")
        return page

    def release_page(self, page: Page):
        """释放已认领的页面。"""
        self._claimed_pages.discard(id(page))

    async def replace_claimed_page(self, page: Page) -> Page:
        """关闭崩溃或长期运行的 Worker 页，并返回已认领的新标签。"""
        was_main_page = page == self._main_page
        self.release_page(page)
        try:
            if not page.is_closed():
                await page.close()
        except Exception:
            pass
        replacement = await self.new_page()
        self._claimed_pages.add(id(replacement))
        if was_main_page:
            self._main_page = replacement
        print(
            f"[BrowserSession:{self._account_id}] "
            "已用新标签替换 Worker 页面"
        )
        return replacement

    async def close_unclaimed_pages(self):
        """关闭未被认领的页面（主页面和已认领的保留）。"""
        for p in list(self._context.pages):
            if p == self._main_page or id(p) in self._claimed_pages:
                continue
            try:
                await p.close()
            except Exception:
                pass

    async def new_page(self) -> Page:
        """从共享 Context 创建新标签页。"""
        page = await self._context.new_page()

        async def _safe_accept(dialog):
            try:
                await dialog.accept()
            except Exception:
                pass
        page.on("dialog", _safe_accept)
        return page

    @staticmethod
    async def _page_is_usable(page: Page) -> bool:
        """崩溃标签通常仍未 closed；用一次轻量脚本调用确认渲染进程可用。"""
        try:
            if page.is_closed():
                return False
            await page.evaluate("1")
            return True
        except Exception:
            return False

    def track_transient_page(self, page: Page):
        """登记聊天等短生命周期页面，避免健康检查误关闭。"""
        self._transient_page_ids.add(id(page))

    def untrack_transient_page(self, page: Page):
        """解除短生命周期页面登记。"""
        self._transient_page_ids.discard(id(page))

    def transient_page_ids(self) -> set:
        """返回短生命周期页面 ID 快照。"""
        return set(self._transient_page_ids)

    def begin_transient_operation(self) -> bool:
        """登记聊天任务；会话关闭后拒绝新增浏览器操作。"""
        if self._closing:
            return False
        task = asyncio.current_task()
        if task is not None:
            self._transient_tasks.add(task)
        return True

    def end_transient_operation(self):
        """解除当前聊天任务登记。"""
        task = asyncio.current_task()
        if task is not None:
            self._transient_tasks.discard(task)

    async def ensure_login(self) -> dict:
        """确保已登录（首次调用时执行，后续直接返回结果）。"""
        if self._skip_login:
            return {"status": "success",
                    "message": "skip_login=True，跳过登录"}
        if self._login_done:
            return self._login_result or {"status": "success",
                                           "message": "已登录(缓存)"}

        has_credentials = bool(
            self._login_url and self._username and self._password
            and self._login_config
        )
        if not has_credentials:
            self._login_done = True
            self._login_result = {"status": "success",
                                  "message": "无凭证，跳过登录"}
            return self._login_result

        print(f"[BrowserSession:{self._account_id}] ─── 执行登录 ───")

        if not self._force_login:
            if await self._check_logged_in():
                self._login_done = True
                self._login_result = {"status": "success",
                                      "message": "已处于登录态"}
                return self._login_result

        self._login_result = await self._do_login()
        self._login_done = True
        return self._login_result

    def is_login_page(self, url: str) -> bool:
        """判断业务页面是否被重定向回当前账号配置的登录地址。"""
        login_url = (self._login_url or "").strip()
        current_url = (url or "").strip()
        return bool(login_url and current_url.startswith(login_url))

    async def relogin(self, page: Optional[Page] = None) -> dict:
        """运行中登录失效时重新登录，并刷新启动阶段的登录缓存。"""
        if self._skip_login:
            return {
                "status": "failed",
                "message": "skip_login=True，无法执行自动重新登录",
            }
        has_credentials = bool(
            self._login_url and self._username and self._password
            and self._login_config
        )
        if not has_credentials:
            self._login_done = False
            self._login_result = None
            return {
                "status": "failed",
                "message": "检测到登录失效，但未配置完整登录凭证",
            }

        async with self._relogin_lock:
            target_page = page or self._main_page
            if target_page is None:
                return {
                    "status": "failed",
                    "message": "检测到登录失效，但没有可用的登录页面",
                }

            print(
                f"[BrowserSession:{self._account_id}] "
                "检测到运行中登录失效，开始重新登录"
            )
            from monitor.browser.login import do_login_async
            result = await do_login_async(
                page=target_page,
                login_url=self._login_url,
                username=self._username,
                password=self._password,
                login_config=self._login_config,
                account_id=self._account_id,
                login_type=self._login_type,
                my_page_url=self._my_page_url,
                force_login=True,
                stop_event=self._stop_event,
            )
            self._login_result = result
            self._login_done = result.get("status") == "success"
            return result

    async def _check_logged_in(self) -> bool:
        """检测是否已登录（委托公共方法）。"""
        from monitor.browser.login import check_already_logged_in_async
        return await check_already_logged_in_async(self._main_page, self._my_page_url)

    async def _do_login(self) -> dict:
        """执行登录操作（委托公共方法 login_handler.do_login_async）。

        注意：调用方（ensure_login / post_login_check）在调用本方法前
        已确认需要登录，因此始终 force_login=True，避免 do_login_async
        内部重复检测登录态导致跳过实际登录。
        """
        from monitor.browser.login import do_login_async
        return await do_login_async(
            page=self._main_page,
            login_url=self._login_url,
            username=self._username,
            password=self._password,
            login_config=self._login_config,
            account_id=self._account_id,
            login_type=self._login_type,
            my_page_url=self._my_page_url,
            force_login=True,
            stop_event=self._stop_event,
        )

    async def get_main_page(self) -> Page:
        """获取主页面。"""
        return self._main_page

    async def get_context(self) -> BrowserContext:
        """获取浏览器上下文。"""
        return self._context

    async def shutdown(self, reason: str):
        """仅在用户主动终止监控时关闭浏览器并上传配置。"""
        if reason != "user_cancel":
            print(f"[BrowserSession:{self._account_id}] 忽略非主动终止的关闭请求: {reason}")
            return False
        await self._close_async()
        from monitor.browser.audio import stop_speech
        stop_speech()
        return True

    def release(self):
        """递减引用计数，归零时安排异步关闭。"""
        with _registry_lock:
            self._refcount -= 1
            if self._refcount > 0:
                print(f"[BrowserSession:{self._account_id}] "
                      f"refcount={self._refcount}")
                return
            _registry.pop(self._account_id, None)

    def close(self):
        """强制移除注册表（不触发异步关闭，由调用方自行 await shutdown()）。"""
        with _registry_lock:
            _registry.pop(self._account_id, None)

    async def _close_async(self):
        """安全关闭浏览器并上传配置到 RustFS。"""
        account_id = self._account_id
        self._closing = True
        current = asyncio.current_task()
        active_tasks = [
            task for task in self._transient_tasks
            if task is not current and not task.done()
        ]
        for task in active_tasks:
            task.cancel()
        if active_tasks:
            await asyncio.gather(*active_tasks, return_exceptions=True)
        try:
            await asyncio.sleep(2)
        except Exception:
            pass
        try:
            if self._context:
                await self._context.close()
        except Exception:
            pass
        try:
            if self._browser:
                await self._browser.close()
        except Exception:
            pass
        try:
            if self._playwright:
                await self._playwright.stop()
        except Exception:
            pass
        try:
            user_data_dir = os.path.join(_USER_DATA_ROOT,
                                         str(account_id))
            storage_sync.upload(account_id, user_data_dir)
        except Exception:
            pass
        print(f"[BrowserSession:{account_id}] 浏览器已关闭并上传配置")

    # ── 内部 ──

    def _add_ref(self):
        self._refcount += 1

    @staticmethod
    def _stopped(stop_event: Optional[threading.Event]) -> bool:
        return stop_event is not None and stop_event.is_set()
