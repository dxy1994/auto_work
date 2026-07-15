"""
BrowserSession — 按账户共享浏览器上下文，支持多页面并行。

职责：
  - 同一 account_id 全局共享一个浏览器上下文（单例注册表）
  - 提供 new_page() 创建独立标签页，线程安全
  - 登录只执行一次，后续页面复用 Cookie / Storage
  - 生命周期管理：引用计数 → 最后关闭时上传配置到 RustFS

使用方式：
  session = BrowserSession.get_or_create(account_id, login_params, headless)
  page1 = session.new_page()
  page2 = session.new_page()
  ...
  session.release()  # 每个调用方退出时递减引用计数
"""

import os
import threading
from typing import Optional, Dict

from patchright.sync_api import sync_playwright, Page, Browser, BrowserContext

import config
from automation.browser import launch_browser
from automation.cookie_reader import save_from_context
from automation.login_handler import do_login
import storage_sync

PLAYWRIGHT_HEADLESS = config.PLAYWRIGHT_HEADLESS

# ── 全局注册表 ──
_registry: Dict[int, 'BrowserSession'] = {}
_registry_lock = threading.Lock()


class BrowserSession:
    """一个账户一个浏览器上下文，多页面共享。"""

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

        # ── 启动浏览器 ──
        self._playwright = sync_playwright().start()
        self._browser, self._context, self._main_page = launch_browser(
            self._playwright,
            headless=self._headless,
            slow_mo=300 if not self._headless else 0,
            account_id=account_id,
        )

        # 自动关闭弹窗
        def _safe_accept(dialog):
            try:
                dialog.accept()
            except Exception:
                pass
        self._main_page.on("dialog", _safe_accept)

        print(f"[BrowserSession:{account_id}] 浏览器已启动, "
              f"main_page={self._main_page.url}")

    # ── 公共 API ──

    @property
    def account_id(self) -> int:
        return self._account_id

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
                    account_id=account_id,
                    login_url=login_url,
                    username=username,
                    password=password,
                    login_type=login_type,
                    login_config=login_config,
                    skip_login=skip_login,
                    force_login=force_login,
                    website_id=website_id,
                    my_page_url=my_page_url,
                    stop_event=stop_event,
                    headless=headless,
                )
                _registry[account_id] = session
            session._add_ref()
            return session

    def new_page(self) -> Page:
        """从共享 Context 创建新标签页。线程安全。"""
        with self._lock:
            page = self._context.new_page()

            def _safe_accept(dialog):
                try:
                    dialog.accept()
                except Exception:
                    pass
            page.on("dialog", _safe_accept)

            return page

    def ensure_login(self) -> dict:
        """确保已登录（首次调用时执行，后续直接返回结果）。"""
        if self._skip_login:
            return {"status": "success", "message": "skip_login=True，跳过登录"}
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
        self._login_result = do_login(
            page=self._main_page,
            login_url=self._login_url,
            username=self._username,
            password=self._password,
            login_config=self._login_config,
            website_id=self._website_id,
            account_id=self._account_id,
            login_type=self._login_type,
            my_page_url=self._my_page_url,
            force_login=self._force_login,
            stop_event=self._stop_event,
        )
        self._login_done = True
        if self._login_result.get("status") != "success":
            print(f"[BrowserSession:{self._account_id}] ❌ 登录失败: "
                  f"{self._login_result.get('message')}")
        return self._login_result

    def get_main_page(self) -> Page:
        """获取主页面。"""
        return self._main_page

    def get_context(self) -> BrowserContext:
        """获取浏览器上下文。"""
        return self._context

    def release(self):
        """递减引用计数，归零时关闭浏览器并上传配置。"""
        with _registry_lock:
            self._refcount -= 1
            if self._refcount > 0:
                print(f"[BrowserSession:{self._account_id}] "
                      f"refcount={self._refcount}")
                return
            # 引用归零 → 关闭
            print(f"[BrowserSession:{self._account_id}] 引用归零，关闭浏览器")
            _registry.pop(self._account_id, None)

        self._close()

    def close(self):
        """强制关闭（忽略引用计数）。"""
        with _registry_lock:
            _registry.pop(self._account_id, None)
        self._close()

    # ── 内部 ──

    def _add_ref(self):
        self._refcount += 1

    def _close(self):
        """安全关闭浏览器并上传配置到 RustFS。"""
        account_id = self._account_id
        try:
            self._main_page.wait_for_timeout(2000)
        except Exception:
            pass
        # 保存 Cookie
        try:
            save_from_context(self._context, account_id)
        except Exception:
            pass
        # 关闭上下文
        try:
            self._context.close()
        except Exception:
            pass
        # 关闭浏览器
        try:
            self._browser.close()
        except Exception:
            pass
        # 关闭 Playwright
        try:
            self._playwright.stop()
        except Exception:
            pass
        # 上传到 RustFS
        try:
            user_data_dir = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "..", "user_data", str(account_id))
            storage_sync.upload(account_id, user_data_dir)
        except Exception:
            pass
        print(f"[BrowserSession:{account_id}] 浏览器已关闭并上传配置")
