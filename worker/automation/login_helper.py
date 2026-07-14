"""
登录操作共享模块（worker 端）
提供浏览器登录的核心步骤（导航、填表、提交），供 browser.py 和 order_monitor.py 共用。
"""
from patchright.sync_api import Page

# ── 选择器默认值 ──
DEFAULT_USERNAME_SEL = "input[name='username']"
DEFAULT_PASSWORD_SEL = "input[name='password']"
DEFAULT_SUBMIT_SEL = "button[type='submit']"


def navigate_and_fill_form(page: Page, url: str, username: str, password: str,
                           login_config: dict):
    """导航到登录页并填充用户名和密码（不点击提交）"""
    username_sel = login_config.get("username_selector", DEFAULT_USERNAME_SEL)
    password_sel = login_config.get("password_selector", DEFAULT_PASSWORD_SEL)

    page.goto(url, wait_until="commit", timeout=60000)
    page.wait_for_timeout(2000)

    page.wait_for_selector(username_sel, timeout=10000)
    page.fill(username_sel, username)

    page.wait_for_selector(password_sel, timeout=10000)
    page.fill(password_sel, password)


def submit_and_wait(page: Page, login_config: dict) -> str:
    """点击提交按钮并等待页面导航完成，返回当前 URL

    部分站点（如 itemmania）采用 AJAX 登录 + 延迟 JS 重定向，点击后不会立即跳转，
    若只等一次 networkidle 就读 URL，会在重定向前误判为登录失败。
    因此先等待 URL 真正离开登录页，给足够的时间。
    """
    submit_sel = login_config.get("submit_selector", DEFAULT_SUBMIT_SEL)

    before_url = page.url
    page.click(submit_sel)

    # 等待页面真正跳转离开登录页（AJAX 登录后 JS 重定向可能有延迟）
    try:
        page.wait_for_url(lambda u: u != before_url, timeout=20000)
    except Exception:
        pass

    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass

    # 再给一次缓冲，防止延迟重定向未完成
    page.wait_for_timeout(1500)

    return page.url


def is_login_success(current_url: str, original_url: str, success_url: str = "") -> bool:
    """判断登录是否成功（依据 URL 变化）"""
    if success_url and success_url in current_url:
        return True
    if not success_url and current_url != original_url:
        return True
    return False
