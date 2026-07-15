"""
登录处理模块。

提供订单监控中公用的异步登录辅助函数：
  - check_already_logged_in_async: 检测浏览器会话是否已处于登录态
  - do_login_async: 执行登录操作（含登录态检测、captcha 手动登录、form 自动登录）
  - _do_manual_login_on_page_async: captcha 手动登录核心逻辑
  - _do_form_login_on_page_async: form 自动登录核心逻辑
"""

import asyncio
import time
from typing import Optional

from patchright.async_api import Page as AsyncPage


# ── Async 版本（供 browser_session 等异步模块调用）──

async def check_already_logged_in_async(page: AsyncPage, my_page_url: str) -> bool:
    """异步版 check_already_logged_in。

    策略：goto 用 domcontentloaded 等待 DOM 就绪（重定向在此阶段完成），
    再短暂等待 JS 层面的延迟跳转，然后直接取 URL 判断。
    不再等 networkidle，因为韩国交易站持续有广告/分析请求，永远不会 idle。
    """
    if not my_page_url:
        print(f"[LoginCheck] 未配置 my_page_url，跳过登录态检测")
        return False
    print(f"[LoginCheck] 尝试进入我的页面检测登录态: {my_page_url}")
    try:
        await page.goto(my_page_url, wait_until="domcontentloaded", timeout=30000)
        # 给 JS 层面的延迟重定向一点时间（如 MetaRefresh、client-side redirect）
        await asyncio.sleep(3)
        current_url = page.url
        print(f"[LoginCheck] 导航完成，当前URL: {current_url}")
        parent_path = my_page_url.rsplit('/', 1)[0]
        if my_page_url in current_url or current_url.startswith(parent_path):
            print(f"[LoginCheck] ✅ 已处于登录态（URL匹配），跳过登录")
            return True
        _LOGIN_KEYWORDS = ("login", "signin", "sign-in", "auth/")
        url_lower = current_url.lower()
        if any(kw in url_lower for kw in _LOGIN_KEYWORDS):
            print(f"[LoginCheck] ❌ 未登录，被重定向到登录页: {current_url}")
            return False
        print(f"[LoginCheck] ⚠️ URL不完全匹配但未跳转到登录页，视为已登录: {current_url}")
        return True
    except Exception as e:
        print(f"[LoginCheck] ⚠️ 检测登录态异常: {e}")
        return False


async def _do_manual_login_on_page_async(
    page: AsyncPage, login_url: str, username: str, password: str,
    login_config: dict, account_id: int, stop_event=None,
) -> dict:
    """
    异步版手动登录（captcha 类型）。
    - 导航到登录页并自动填充用户名和密码
    - 等待人工完成验证码并手动点击登录
    - 每 10s 语音播报提醒
    - 轮询检测页面跳转判断登录成功
    """
    start = time.time()
    MANUAL_TIMEOUT = 300
    POLL_INTERVAL = 3

    username_sel = login_config.get("username_selector", "input[name='username']")
    password_sel = login_config.get("password_selector", "input[name='password']")
    success_url = login_config.get("success_url", "")

    # 1. 导航到登录页
    await page.goto(login_url, wait_until="commit", timeout=60000)
    await asyncio.sleep(2)

    # 2. 自动填充用户名和密码
    try:
        await page.wait_for_selector(username_sel, timeout=5000)
        await page.fill(username_sel, username)
    except Exception:
        pass
    try:
        await page.wait_for_selector(password_sel, timeout=5000)
        await page.fill(password_sel, password)
    except Exception:
        pass

    print(f"[ManualLogin] 表单已填充，请在浏览器中手动完成验证码并登录")
    from automation.audio_alert import play_alert_audio
    play_alert_audio(text=f"账号{account_id}需要登录验证码，请查看浏览器")

    # 3. 轮询等待用户手动完成登录
    login_page_url = page.url
    last_alert_time = time.time()
    while (time.time() - start) < MANUAL_TIMEOUT:
        if stop_event is not None:
            if stop_event.is_set():
                return {
                    "status": "cancelled",
                    "message": "登录任务已停止",
                    "duration_ms": int((time.time() - start) * 1000),
                }

        # 页面存活检测（page.url 是缓存属性，进程崩溃时可能不抛异常，
        # 必须用 evaluate 与浏览器进程 IPC 通信才能真正判断存活）
        try:
            await page.evaluate("1")
        except Exception:
            print("[ManualLogin] 页面已断开，停止等待")
            break

        await asyncio.sleep(POLL_INTERVAL)
        # 每 10s 重复播报一次语音提醒（播报前再确认一次页面存活）
        now = time.time()
        if now - last_alert_time >= 10:
            try:
                await page.evaluate("1")
            except Exception:
                print("[ManualLogin] 页面已断开，停止播报")
                break
            play_alert_audio(text=f"账号{account_id}需要登录验证码，请查看浏览器")
            last_alert_time = now
        try:
            current_url = page.url
        except Exception:
            break
        if success_url and success_url in current_url:
            await asyncio.sleep(2)
            try:
                await page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            return {
                "status": "success",
                "message": f"手动登录成功，当前页面：{current_url}",
                "duration_ms": int((time.time() - start) * 1000),
            }
        if current_url != login_page_url and current_url != login_url:
            await asyncio.sleep(2)
            try:
                await page.wait_for_load_state("networkidle", timeout=15000)
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


async def do_login_async(
    page: AsyncPage, login_url: str, username: str, password: str,
    login_config: dict, account_id: int,
    login_type: str = "form", my_page_url: str = "",
    force_login: bool = False, stop_event=None,
) -> dict:
    """
    异步版 do_login：先检测登录态，再按类型执行登录。
    - captcha 类型 → _do_manual_login_on_page_async（含语音提醒）
    - form 类型 → 自动填充表单并提交
    """
    print(f"[DoLogin] ─── 开始登录流程 ───")
    print(f"[DoLogin] 账号ID={account_id}, 登录类型={login_type}, 强制登录={force_login}")
    print(f"[DoLogin] 登录URL={login_url}")

    # ── 0. 先检测是否已登录 ──
    if not force_login:
        print(f"[DoLogin] 步骤1: 检测是否已登录...")
        if await check_already_logged_in_async(page, my_page_url):
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
        result = await _do_manual_login_on_page_async(
            page, login_url, username, password, login_config,
            account_id, stop_event=stop_event,
        )
    else:
        print(f"[DoLogin] 使用自动登录模式 (form)")
        result = await _do_form_login_on_page_async(
            page, login_url, username, password, login_config,
            account_id, stop_event=stop_event,
        )
    print(f"[DoLogin] ─── 登录流程结束: {result['status']} - {result['message']} ───")
    return result


async def _do_form_login_on_page_async(
    page: AsyncPage, login_url: str, username: str, password: str,
    login_config: dict, account_id: int, stop_event=None,
) -> dict:
    """异步版自动表单登录。"""
    start = time.time()
    username_sel = login_config.get("username_selector", "input[name='username']")
    password_sel = login_config.get("password_selector", "input[name='password']")
    submit_sel = login_config.get("submit_selector", "button[type='submit']")
    success_url = login_config.get("success_url", "")

    try:
        await page.goto(login_url, wait_until="commit", timeout=60000)
        await asyncio.sleep(2)
        await page.wait_for_selector(username_sel, timeout=10000)
        await page.fill(username_sel, username)
        await page.wait_for_selector(password_sel, timeout=10000)
        await page.fill(password_sel, password)

        before_url = page.url
        await page.click(submit_sel)
        try:
            await page.wait_for_url(lambda u: u != before_url, timeout=20000)
        except Exception:
            pass
        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await asyncio.sleep(1.5)
        current_url = page.url

        if success_url and success_url in current_url:
            return {"status": "success",
                    "message": f"登录成功: {current_url}",
                    "duration_ms": int((time.time() - start) * 1000)}
        if not success_url and current_url != login_url:
            return {"status": "success",
                    "message": f"登录成功(页面跳转): {current_url}",
                    "duration_ms": int((time.time() - start) * 1000)}
        return {"status": "failed",
                "message": "登录可能失败，页面未跳转",
                "duration_ms": int((time.time() - start) * 1000)}
    except Exception as e:
        return {"status": "failed",
                "message": f"登录异常: {e}",
                "duration_ms": int((time.time() - start) * 1000)}
