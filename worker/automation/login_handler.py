"""
登录处理模块。

提供订单监控中公用的登录辅助函数：
  - check_already_logged_in: 检测浏览器会话是否已处于登录态
  - do_login: 执行登录操作（自动/手动），含登录态检测、强制登录等

这些函数从 order_monitor 中抽离出来，供各站点监控逻辑复用。
"""

import time
from typing import Optional

from patchright.sync_api import Page

from automation.browser import perform_login


def check_already_logged_in(page: Page, my_page_url: str) -> bool:
    """
    检测当前持久化浏览器会话是否已处于登录态。
    导航到「我的页面」，通过 URL 匹配 + 登录页关键词检测判断是否已登录。

    针对慢速韩国站点（含 reCAPTCHA/广告 iframe）：
    - 使用 wait_until="commit" 快速进入响应阶段，避免 domcontentloaded 被外部资源阻塞而挂起
    - 预留足够的结算/重定向时间，避免在页面跳转前就误判
    - 增加登录页关键词检测，避免因 URL 不完全匹配而误判
    """
    if not my_page_url:
        print(f"[LoginCheck] 未配置 my_page_url，跳过登录态检测")
        return False
    print(f"[LoginCheck] 尝试进入我的页面检测登录态: {my_page_url}")
    try:
        page.goto(my_page_url, wait_until="commit", timeout=60000)
        # 等待页面结算（可能发生重定向到登录页），给够时间
        page.wait_for_timeout(5000)
        try:
            page.wait_for_load_state("domcontentloaded", timeout=20000)
        except Exception:
            pass
        try:
            page.wait_for_load_state("networkidle", timeout=20000)
        except Exception:
            pass
        # 再给一次缓冲，防止延迟重定向
        page.wait_for_timeout(2000)
        current_url = page.url
        print(f"[LoginCheck] 导航完成，当前URL: {current_url}")

        # ── 判断逻辑 ──
        # 1. URL 完全包含目标地址，或在同一父路径下 → 未被重定向到别处，已登录
        parent_path = my_page_url.rsplit('/', 1)[0]
        if my_page_url in current_url or current_url.startswith(parent_path):
            print(f"[LoginCheck] ✅ 已处于登录态（URL匹配），跳过登录")
            return True

        # 2. 页面被重定向到含登录关键词的 URL → 确认未登录
        _LOGIN_KEYWORDS = ("login", "signin", "sign-in", "auth/")
        url_lower = current_url.lower()
        if any(kw in url_lower for kw in _LOGIN_KEYWORDS):
            print(f"[LoginCheck] ❌ 未登录，被重定向到登录页: {current_url}")
            return False

        # 3. URL 不匹配目标但也未跳转到登录页 → 可能已登录（站点内部跳转）
        print(f"[LoginCheck] ⚠️ URL不完全匹配但未跳转到登录页，视为已登录: {current_url}")
        return True
    except Exception as e:
        print(f"[LoginCheck] ⚠️ 检测登录态异常: {e}")
        return False


def do_login(page: Page, login_url: str, username: str, password: str,
             login_config: dict, website_id: int, account_id: int,
             login_type: str = "form", my_page_url: str = "",
             force_login: bool = False, stop_event=None) -> dict:
    """
    在当前 page 上执行登录操作。
    先尝试进入「我的页面」检测当前会话是否已登录，若已登录则跳过。
    - force_login=True: 跳过已登录检测，强制执行登录（用于页面提示需重新登录的场景）
    - login_type == "captcha": 手动登录（表单填充后等待人工完成验证码并登录）
    - 其他类型: 委托 browser.perform_login 自动登录
    """
    print(f"[DoLogin] ─── 开始登录流程 ───")
    print(f"[DoLogin] 账号ID={account_id}, 网站ID={website_id}, 登录类型={login_type}, 强制登录={force_login}")
    print(f"[DoLogin] 登录URL={login_url}")

    # ── 0. 先检测是否已登录（尝试进入我的页面，未重定向则已登录）──
    if not force_login:
        print(f"[DoLogin] 步骤1: 检测是否已登录...")
        if check_already_logged_in(page, my_page_url):
            print(f"[DoLogin] ─── 登录流程结束（已登录，跳过）───")
            return {
                "status": "success",
                "message": "当前会话已处于登录态，跳过登录",
                "duration_ms": 0,
            }
    else:
        print(f"[DoLogin] 强制登录模式，跳过已登录检测")

    print(f"[DoLogin] 步骤2: 执行登录操作...")
    if login_type == "captcha":
        print(f"[DoLogin] 使用手动登录模式 (captcha)")
        result = _do_manual_login_on_page(
            page, login_url, username, password, login_config,
            website_id, account_id, stop_event=stop_event,
        )
    else:
        print(f"[DoLogin] 使用自动登录模式 (form)")
        result = perform_login(
            page, login_url, username, password, login_config,
            website_id, account_id, stop_event=stop_event,
        )
    print(f"[DoLogin] ─── 登录流程结束: {result['status']} - {result['message']} ───")
    return result


def _do_manual_login_on_page(page: Page, login_url: str, username: str, password: str,
                              login_config: dict, website_id: int, account_id: int,
                              stop_event=None) -> dict:
    """
    在已有 page 上执行手动登录（适用于 captcha 类型网站）：
    - 导航到登录页并自动填充用户名和密码
    - 等待人工完成验证码并手动点击登录
    - 轮询检测页面跳转判断登录成功
    """
    start = time.time()
    MANUAL_TIMEOUT = 300
    POLL_INTERVAL = 3

    username_sel = login_config.get("username_selector", "input[name='username']")
    password_sel = login_config.get("password_selector", "input[name='password']")
    success_url = login_config.get("success_url", "")

    # 1. 导航到登录页
    page.goto(login_url, wait_until="commit", timeout=60000)
    page.wait_for_timeout(2000)

    # 2. 自动填充用户名和密码
    try:
        page.wait_for_selector(username_sel, timeout=5000)
        page.fill(username_sel, username)
    except Exception:
        pass

    try:
        page.wait_for_selector(password_sel, timeout=5000)
        page.fill(password_sel, password)
    except Exception:
        pass

    print(f"[ManualLogin] 表单已填充，请在浏览器中手动完成验证码并登录")

    # 3. 轮询等待用户手动完成登录
    login_page_url = page.url
    while (time.time() - start) < MANUAL_TIMEOUT:
        if stop_event is not None:
            if stop_event.wait(POLL_INTERVAL):
                return {
                    "status": "cancelled",
                    "message": "登录任务已停止",
                    "duration_ms": int((time.time() - start) * 1000),
                }
        else:
            page.wait_for_timeout(POLL_INTERVAL * 1000)
        try:
            current_url = page.url
        except Exception:
            break

        if success_url and success_url in current_url:
            page.wait_for_timeout(2000)
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            return {
                "status": "success",
                "message": f"手动登录成功，当前页面：{current_url}",
                "duration_ms": int((time.time() - start) * 1000),
            }

        if current_url != login_page_url and current_url != login_url:
            page.wait_for_timeout(2000)
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            return {
                "status": "success",
                "message": f"手动登录成功（页面跳转），当前：{current_url}",
                "duration_ms": int((time.time() - start) * 1000),
            }

    return {
        "status": "timeout",
        "message": "手动登录超时，请确认是否已完成登录",
        "duration_ms": int((time.time() - start) * 1000),
    }
