"""
自动登录服务（worker 端）
支持 form（纯表单自动填充）和 captcha（需验证码介入）两种模式

基于 Patchright（Playwright 反检测分支），内置消除所有自动化痕迹。

浏览器持久化策略：
- 有 account_id → 使用 launch_persistent_context，按账号隔离 user_data_dir
  Cookie / localStorage 自动持久化到 worker/user_data/{account_id}/
  通过 --restore-last-session 恢复上次浏览器会话，保留 session cookie，无需重复登录
- 无 account_id → 临时上下文，任务结束丢弃所有数据
"""
import os
import sys
import time
from typing import Optional

from patchright.sync_api import sync_playwright, Page, Browser, BrowserContext

import config
from reporter import get_reporter
from automation.login_helper import (
    navigate_and_fill_form, submit_and_wait, is_login_success,
)
import storage_sync
from automation.cookie_reader import save_from_context

# Docker 环境下需要 headless 模式，本地开发保持 headed
PLAYWRIGHT_HEADLESS = config.PLAYWRIGHT_HEADLESS

# ── 非标准视口尺寸，避免被默认视口指纹识别 ──
VIEWPORT = {"width": 1280, "height": 800}

# ── 浏览器用户数据根目录 ──
_USER_DATA_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "user_data")

# ── 沙箱控制：Playwright/Patchright 默认 chromium_sandbox=False，会自动注入 --no-sandbox
#    导致 Windows/macOS 下弹出"不受支持的命令行标记 --no-sandbox"警告。
#    仅 Linux（Docker/root 场景）需要禁用沙箱；Windows/macOS 应启用沙箱避免该警告。
_CHROMIUM_SANDBOX = sys.platform != "linux"


def launch_browser(p, headless: bool = False, slow_mo: int = 0, args: list = None,
                   account_id: Optional[int] = None):
    """
    启动浏览器。Patchright 推荐 channel 优先（驱动与 Chrome 版本自动匹配），
    磁盘路径作兜底，最后回退内置 Chromium。

    有 account_id 时使用持久化上下文：
      - 用户数据目录: worker/user_data/{account_id}/
      - Cookie / localStorage 自动保存，下次启动复用登录态
    无 account_id 时使用临时上下文（任务结束即丢弃）。

    返回 (browser, context, page)，调用方必须在 finally 中关闭。
    """
    launch_args = (args or []) + [
        "--disable-blink-features=AutomationControlled",
        "--restore-last-session",
    ]

    # ── 1. channel 优先（Patchright 推荐：自动匹配驱动版本）──
    browser_type = None
    for ch in ("chrome", "msedge"):
        try:
            _test = p.chromium.launch(channel=ch, headless=True, args=["--headless"], chromium_sandbox=_CHROMIUM_SANDBOX)
            _test.close()
            browser_type = ch
            print(f"✅ [Browser] channel={ch}")
            break
        except Exception:
            continue

    # ── 2. 构建 launch 共用参数 ──
    launch_kwargs: dict = {
        "headless": headless,
        "slow_mo": slow_mo,
        "args": launch_args,
        "chromium_sandbox": _CHROMIUM_SANDBOX,
    }

    if browser_type:
        launch_kwargs["channel"] = browser_type
    else:
        found_exe = False
        for exe_path in _CHROME_PATHS:
            if os.path.isfile(exe_path):
                launch_kwargs["executable_path"] = exe_path
                print(f"✅ [Browser] exe={exe_path}")
                found_exe = True
                break
        if not found_exe:
            print("⚠️  [Browser] 未找到 Chrome/Edge，使用内置 Chromium")

    # ── 3. 持久化上下文（按 account_id 隔离）──
    if account_id:
        user_data_dir = os.path.join(_USER_DATA_ROOT, str(account_id))
        os.makedirs(user_data_dir, exist_ok=True)
        # 从 RustFS 下载远程配置（本地已有则跳过）
        storage_sync.download(account_id, user_data_dir)
        context = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            viewport=VIEWPORT,
            timezone_id="Asia/Seoul",
            locale="ko-KR",
            **launch_kwargs,
        )
        browser = context.browser
        # --restore-last-session 会恢复上次标签页，同时产生多余的 about:blank
        page = _pick_page_and_close_blanks(context)
        print(f"✅ [Browser] persistent user_data_dir={user_data_dir}")
    else:
        browser = p.chromium.launch(**launch_kwargs)
        context = browser.new_context(
            viewport=VIEWPORT,
            timezone_id="Asia/Seoul",
            locale="ko-KR",
        )
        page = context.new_page()

    return browser, context, page


# ═══════════════════════════════════════════════════════════
# 内部辅助
# ═══════════════════════════════════════════════════════════

def _pick_page_and_close_blanks(context: BrowserContext) -> Page:
    """
    --restore-last-session 恢复会话时 Chromium 会多开一个 about:blank 页。
    只关闭 about:blank，保留所有恢复的真实页面。
    返回最后一个非空白页（最活跃页），若无则返回唯一的 about:blank 页。

    注意：若整个上下文只有一个 about:blank 则不关（关闭会导致浏览器退出）。
    """
    pages = context.pages
    if not pages:
        return context.new_page()

    blanks = [p for p in pages if p.url == "about:blank"]
    non_blanks = [p for p in pages if p.url != "about:blank"]

    if non_blanks:
        # 有真实页面 → 安全关闭所有 about:blank
        for p in blanks:
            try:
                p.close()
            except Exception:
                pass
        return non_blanks[-1]  # 最后一个通常是最近活跃的

    # 没有真实页面，只剩下一个 about:blank → 保留
    if len(blanks) == 1:
        return blanks[0]

    # 多个 about:blank → 保留第一个，关闭其余的
    for p in blanks[1:]:
        try:
            p.close()
        except Exception:
            pass
    return blanks[0]


_CHROME_PATHS = [
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]


def perform_login(
    page: Page,
    url: str,
    username: str,
    password: str,
    login_config: dict,
    website_id: int = None,
    account_id: int = None,
    task_id: str = None,
    stop_event=None,
) -> dict:
    """
    在已有 page 上执行登录操作（不管理浏览器生命周期）。
    传入 task_id 时按 captcha 类型处理：请求前端输入验证码。
    返回: { "status": "success"|"failed"|"captcha_required", "message": str, "duration_ms": int }
    """
    start = time.time()
    success_url = login_config.get("success_url", "")
    captcha_sel = login_config.get("captcha_selector", "")
    captcha_input_sel = login_config.get("captcha_input_selector", "")

    print(f"[PerformLogin] 开始登录: url={url}, success_url={success_url}")

    if stop_event is not None and stop_event.is_set():
        return _stopped_result(start)

    print(f"[PerformLogin] 填充表单...")
    navigate_and_fill_form(page, url, username, password, login_config)
    print(f"[PerformLogin] 表单填充完成")
    if stop_event is not None and stop_event.is_set():
        return _stopped_result(start)

    # 处理验证码
    if task_id and captcha_sel:
        reporter = get_reporter()
        reporter.report_captcha_required(task_id)
        captcha_val = reporter.wait_captcha(task_id, timeout=60)
        if not captcha_val:
            return {
                "status": "captcha_required",
                "message": "验证码超时，未收到输入",
                "duration_ms": int((time.time() - start) * 1000),
            }
        if captcha_input_sel:
            page.wait_for_selector(captcha_input_sel, timeout=10000)
            page.fill(captcha_input_sel, captcha_val)

    print(f"[PerformLogin] 提交表单并等待页面跳转...")
    if stop_event is not None and stop_event.is_set():
        return _stopped_result(start)
    current_url = submit_and_wait(page, login_config)
    print(f"[PerformLogin] 提交后URL: {current_url}")

    if is_login_success(current_url, url, success_url):
        print(f"[PerformLogin] ✅ 登录成功: {current_url}")
        return {
            "status": "success",
            "message": f"登录成功，当前页面：{current_url}",
            "duration_ms": int((time.time() - start) * 1000),
        }

    print(f"[PerformLogin] ❌ 登录可能失败，页面未跳转")
    return {
        "status": "failed",
        "message": "登录可能失败，页面未跳转，请检查账号密码或登录配置",
        "duration_ms": int((time.time() - start) * 1000),
    }


def run_auto_login(
    task_id: str,
    url: str,
    username: str,
    password: str,
    login_type: str,
    login_config: dict,
    website_id: int = None,
    account_id: int = None,
    stop_event=None,
) -> dict:
    """
    创建浏览器并执行自动登录；任务结束后始终关闭浏览器。
    """
    start = time.time()

    with sync_playwright() as p:
        browser, context, page = launch_browser(
            p,
            headless=PLAYWRIGHT_HEADLESS,
            slow_mo=300 if not PLAYWRIGHT_HEADLESS else 0,
            account_id=account_id,
        )

        try:
            result = perform_login(
                page, url, username, password, login_config,
                website_id, account_id,
                task_id=task_id if login_type == "captcha" else None,
                stop_event=stop_event,
            )
            return result
        except Exception as e:
            return {
                "status": "failed",
                "message": f"登录过程异常：{str(e)}",
                "duration_ms": int((time.time() - start) * 1000),
            }
        finally:
            _close_browser(page, browser, account_id=account_id)


def run_manual_login(
    task_id: str,
    url: str,
    username: str,
    password: str,
    login_config: dict,
    website_id: int = None,
    account_id: int = None,
    stop_event=None,
) -> dict:
    """
    手动登录模式（适用于 captcha 类型网站）：
    委托 login_handler._do_manual_login_on_page 执行核心逻辑，
    本函数负责浏览器生命周期管理与事件上报。
    """
    start = time.time()
    reporter = get_reporter()

    with sync_playwright() as p:
        browser, context, page = launch_browser(
            p, headless=False, slow_mo=100, account_id=account_id,
        )

        try:
            from automation.login_handler import _do_manual_login_on_page

            # 通知前端：即将开始手动登录
            reporter.report_event(
                task_id, "manual_login_ready",
                "表单将自动填充，请在浏览器中手动完成验证码并登录",
                account_id,
            )

            result = _do_manual_login_on_page(
                page, url, username, password, login_config,
                website_id, account_id, stop_event=stop_event,
            )

            # 根据结果上报对应事件
            status = result["status"]
            if status == "success":
                reporter.report_event(
                    task_id, "login_success",
                    result["message"], account_id,
                )
            elif status == "timeout":
                reporter.report_event(
                    task_id, "login_timeout",
                    "手动登录超时，请确认是否已完成登录", account_id,
                )
            elif status in ("failed", "cancelled"):
                reporter.report_event(
                    task_id, "login_failed",
                    result["message"], account_id,
                )
            return result

        except Exception as e:
            reporter.report_event(
                task_id, "login_failed",
                f"登录过程异常：{str(e)}", account_id,
            )
            return {
                "status": "failed",
                "message": f"登录过程异常：{str(e)}",
                "duration_ms": int((time.time() - start) * 1000),
            }
        finally:
            _close_browser(page, browser, account_id=account_id)


def _stopped_result(start: float) -> dict:
    return {
        "status": "failed",
        "message": "任务已停止",
        "duration_ms": int((time.time() - start) * 1000),
    }


def sync_upload_profile(account_id: int):
    """上传浏览器配置到 RustFS（供外部直接管理浏览器生命周期的模块调用）。"""
    if account_id:
        user_data_dir = os.path.join(_USER_DATA_ROOT, str(account_id))
        storage_sync.upload(account_id, user_data_dir)


def _close_browser(page: Page, browser, account_id: Optional[int] = None):
    """安全关闭浏览器。持久化上下文会自动保存 Cookie/LocalStorage 到磁盘，
    随后上传到 RustFS 实现跨机器共享。"""
    try:
        page.wait_for_timeout(2000)
    except Exception:
        pass
    # ── 保存 Cookie 到 JSON（供 http_monitor 无浏览器使用）──
    ctx = page.context if page else None
    if account_id and ctx:
        try:
            save_from_context(ctx, account_id)
        except Exception:
            pass
    try:
        if ctx:
            ctx.close()
    except Exception:
        pass
    try:
        if browser:
            browser.close()
    except Exception:
        pass
    # ── 上传到 RustFS ──
    if account_id:
        user_data_dir = os.path.join(_USER_DATA_ROOT, str(account_id))
        storage_sync.upload(account_id, user_data_dir)
