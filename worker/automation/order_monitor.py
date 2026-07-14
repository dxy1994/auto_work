"""
订单查询与提醒服务（worker 端）
根据传入的 website_id，执行不同的业务逻辑：
  - website_id == 1: itemmania 监控
  - website_id == 2: barotem 监控
  - website_id == 3: itembay 监控
  - 其他 website_id: 预留扩展

各站点的选择器/页面等业务配置（order_cfg）保留在本模块内，总控只负责下发
账号凭证与登录配置。

公共方法：
  - play_alert_audio(audio_path=None, text=None): 播放提醒音频，优先文字转语音，其次自定义文件
"""
import datetime
import re
import threading
import time
from pathlib import Path
from typing import Optional

from patchright.sync_api import sync_playwright, Page

import config
from automation.login_helper import is_login_success
from automation.browser import perform_login, launch_browser, sync_upload_profile
import cookie_reader

# 项目根目录（worker 的上一级），用于解析可选的自定义音频文件
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Docker 环境下需要 headless 模式，本地开发保持 headed
PLAYWRIGHT_HEADLESS = config.PLAYWRIGHT_HEADLESS


# ═══════════════════════════════════════════════════════════════════════════════
# 公共方法：播放提醒音频
# ═══════════════════════════════════════════════════════════════════════════════

def play_alert_audio(audio_path: Optional[str] = None, text: Optional[str] = None) -> bool:
    """
    播放提醒音频的公共方法，其他模块可直接调用。

    优先级：
      1. 如果 text 有值 → pyttsx3 文字转语音播放
      2. 如果 audio_path 有效且文件存在 → 使用 pygame / playsound 播放
      3. 否则 → 系统蜂鸣（Windows winsound / 终端 \a）

    参数:
        audio_path: 音频文件相对于项目根目录的路径，如 "uploads/audio/abc.mp3"
                   传 None 或不传则使用系统蜂鸣回退
        text:       要转语音的文本字符串，传 None 或不传则跳过 TTS

    返回:
        bool: True 表示成功播放（含回退），False 表示所有方式均失败
    """
    # ── 1. 尝试文字转语音 ──
    if text:
        if _play_tts(text):
            return True
        # TTS 失败，继续回退到音频文件

    # ── 2. 尝试播放自定义音频文件 ──
    if audio_path:
        full_path = PROJECT_ROOT / audio_path
        if full_path.exists():
            if _play_audio_file(str(full_path)):
                return True
            # 文件存在但播放失败，继续回退到蜂鸣

    # ── 3. 回退：系统蜂鸣 ──
    return _play_system_beep()


def _play_audio_file(file_path: str) -> bool:
    """
    播放音频文件，尝试多种后端。
    所有方案均放入守护线程，确保阻塞式播放不会被 executor 回收 kill 掉。
    """
    # 方案A: pygame（守护线程轮询播放状态，pygame>=2.6 对 Python 3.12 兼容最佳）
    try:
        import pygame

        def _pygame_play():
            pygame.mixer.init()
            pygame.mixer.music.load(file_path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)

        t = threading.Thread(target=_pygame_play, daemon=True)
        t.start()
        time.sleep(0.3)
        print(f"[Audio] pygame 播放中: {file_path}")
        return True
    except Exception as e:
        print(f"[Audio] pygame 不可用: {e}")

    # 方案C: Windows Media Player (win32com)
    try:
        from win32com.client import Dispatch

        def _wmplayer_play():
            mp = Dispatch("WMPlayer.OCX")
            mp.URL = file_path
            mp.controls.play()
            import pythoncom
            while mp.playState != 1:  # 1 = Stopped
                pythoncom.PumpWaitingMessages()
                time.sleep(0.1)

        t = threading.Thread(target=_wmplayer_play, daemon=True)
        t.start()
        time.sleep(0.3)
        print(f"[Audio] WMPlayer 播放中: {file_path}")
        return True
    except Exception as e:
        print(f"[Audio] WMPlayer 不可用: {e}")

    print(f"[Audio] 所有播放后端均失败: {file_path}")
    return False


def _play_system_beep() -> bool:
    """系统蜂鸣回退"""
    try:
        import winsound
        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        time.sleep(0.3)
        winsound.Beep(1000, 500)
        time.sleep(0.1)
        winsound.Beep(1200, 500)
        time.sleep(0.1)
        winsound.Beep(1000, 500)
        return True
    except ImportError:
        print("\a" * 3)
        return True


def _play_tts(text: str) -> bool:
    """
    使用 pyttsx3 将文字转为语音并播放。
    放入守护线程执行，避免阻塞主流程。
    """
    try:
        import pyttsx3

        def _tts_speak():
            engine = pyttsx3.init()
            engine.say(text)
            engine.runAndWait()

        t = threading.Thread(target=_tts_speak, daemon=True)
        t.start()
        time.sleep(0.3)
        print(f"[Audio] pyttsx3 播放中: {text[:30]}{'...' if len(text) > 30 else ''}")
        return True
    except Exception as e:
        print(f"[Audio] pyttsx3 不可用: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# 业务逻辑分发
# ═══════════════════════════════════════════════════════════════════════════════

def run_order_check(
    task_id: str,
    website_id: int,
    account_id: int,
    url: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    login_type: str = "form",
    login_config: Optional[dict] = None,
    stop_event: Optional[threading.Event] = None,
):
    """
    根据 website_id 分发到不同业务逻辑。

    参数:
        task_id:      任务ID
        website_id:   网站ID
        account_id:   账号ID
        url:          登录页URL
        username:     用户名
        password:     登录密码（明文，由总控解密后下发）
        login_type:   登录类型 form/captcha
        login_config: 登录配置
        stop_event:   用于外部终止任务的 threading.Event，为 None 则不可终止
    """
    start = time.time()
    login_url = url
    login_config = login_config or {}
    has_credentials = bool(login_url and username and password)
    result = None

    cred_status = "有" if has_credentials else "无"
    print(f"[OrderCheck] ═══ 开始订单检查 ═══")
    print(f"[OrderCheck] 账号ID={account_id}, 用户名={username}, 网站ID={website_id}, 登录类型={login_type}")
    print(f"[OrderCheck] 登录URL={login_url}, 凭证={cred_status}")

    try:

        if website_id == 1:
            order_cfg = {
                "my_page_url": "https://www.itemmania.com/myroom/sell/sell_regist.html",
                "my_page_selector": "#g_BODY > header > div > div.header-nav-wrapper > nav > a:nth-child(4)",
                "order_count_selector": "#nav_sub_sell > li:nth-child(2) > a > span:nth-child(2)",
                "wait_timeout": 10000,
                "refresh_interval": 3,
                "max_retries": 999,
            }
            print(f"[OrderCheck] 分发到 itemmania 监控逻辑")
            result = _check_website_1(
                order_cfg=order_cfg,
                start=start,
                login_url=login_url if has_credentials else None,
                username=username if has_credentials else None,
                password=password if has_credentials else None,
                login_config=login_config,
                login_type=login_type,
                stop_event=stop_event,
                account_id=account_id,
                website_id=website_id,
            )
        # ── 其他网站扩展入口 ──
        elif website_id == 2:
            order_cfg = {
                "my_page_url": "https://www.barotem.com/mypage",
                "my_page_selector": "",
                "order_count_selector": "body > main > div.mypage_container > nav > div > ul:nth-child(1) > li:nth-child(2) > a > span",
                "wait_timeout": 10000,
                "refresh_interval": 3,
                "max_retries": 999,
            }

            print(f"[OrderCheck] 分发到 barotem 监控逻辑")
            result = _check_website_2(order_cfg=order_cfg,
                start=start,
                login_url=login_url if has_credentials else None,
                username=username if has_credentials else None,
                password=password if has_credentials else None,
                login_config=login_config,
                login_type=login_type,
                stop_event=stop_event,
                account_id=account_id,
                website_id=website_id,)
        elif website_id == 3:
            order_cfg = {
                "my_page_url": "https://www.itembay.com/mybay/status/mybayStatusSellList",
                "my_page_selector": "",
                "order_count_selector": "#nav_sub_sell > li:nth-child(1) > a > span:nth-child(2)",
                "wait_timeout": 10000,
                "refresh_interval": 3,
                "max_retries": 999,
            }

            print(f"[OrderCheck] 分发到 itemBay 监控逻辑")
            result = _check_website_3(order_cfg=order_cfg,
                start=start,
                login_url=login_url if has_credentials else None,
                username=username if has_credentials else None,
                password=password if has_credentials else None,
                login_config=login_config,
                login_type=login_type,
                stop_event=stop_event,
                account_id=account_id,
                website_id=website_id,)
        else:
            result = {
                "status": "skipped",
                "message": f"网站 ID {website_id} 未配置订单查询逻辑",
                "order_count": 0,
                "duration_ms": int((time.time() - start) * 1000),
            }
    except Exception as e:
        result = {
            "status": "failed",
            "message": f"订单查询异常：{str(e)}",
            "order_count": 0,
            "duration_ms": int((time.time() - start) * 1000),
        }
    finally:
        elapsed = int((time.time() - start) * 1000)
        status = result.get('status', 'unknown') if result else 'no_result'
        msg = result.get('message', '') if result else ''
        print(f"[OrderCheck] ═══ 订单检查结束 ═══")
        print(f"[OrderCheck] 账号ID={account_id}, 状态={status}, 耗时={elapsed}ms")
        print(f"[OrderCheck] 结果: {msg}")
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# 登录辅助（各站点共用）
# ═══════════════════════════════════════════════════════════════════════════════

def _check_already_logged_in(page: Page, my_page_url: str) -> bool:
    """
    检测当前临时浏览器会话是否已处于登录态。
    导航到「我的页面」，如果页面没有被重定向（URL 仍包含 my_page_url），说明已登录。

    针对慢速韩国站点（含 reCAPTCHA/广告 iframe）：
    - 使用 wait_until="commit" 快速进入响应阶段，避免 domcontentloaded 被外部资源阻塞而挂起
    - 预留足够的结算/重定向时间，避免在页面跳转前就误判
    """
    if not my_page_url:
        print(f"[LoginCheck] 未配置 my_page_url，跳过登录态检测")
        return False
    print(f"[LoginCheck] 尝试进入我的页面检测登录态: {my_page_url}")
    try:
        page.goto(my_page_url, wait_until="commit", timeout=60000)
        # 等待页面结算（可能发生重定向到登录页），给够时间
        page.wait_for_timeout(4000)
        try:
            page.wait_for_load_state("domcontentloaded", timeout=20000)
        except Exception:
            pass
        try:
            page.wait_for_load_state("networkidle", timeout=20000)
        except Exception:
            pass
        # 再给一次缓冲，防止延迟重定向
        page.wait_for_timeout(1500)
        current_url = page.url
        print(f"[LoginCheck] 导航完成，当前URL: {current_url}")
        # 页面没有被重定向到其他地方，说明已登录
        if my_page_url in current_url or current_url.startswith(my_page_url.rsplit('/', 1)[0]):
            print(f"[LoginCheck] ✅ 已处于登录态，跳过登录")
            return True
        print(f"[LoginCheck] ❌ 未登录，页面被重定向到: {current_url}")
        return False
    except Exception as e:
        print(f"[LoginCheck] ⚠️ 检测登录态异常: {e}")
        return False


def _do_login(page: Page, login_url: str, username: str, password: str,
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
        if _check_already_logged_in(page, my_page_url):
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


# ═══════════════════════════════════════════════════════════════════════════════
# website_id == 1 (itemmania) 的业务逻辑
# ═══════════════════════════════════════════════════════════════════════════════

def _check_website_1(
    order_cfg: dict,
    start: float,
    login_url: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    login_config: Optional[dict] = None,
    login_type: str = "form",
    stop_event: Optional[threading.Event] = None,
    account_id: Optional[int] = None,
    website_id: Optional[int] = None,
) -> dict:
    """
    持续循环监控订单：
    1. 自动登录 → 进入"我的页面"
    2. 循环刷新页面 → 检测订单数量 → 有单播放提醒
    3. 出现不可控异常 → 重新走完整流程（登录→我的页面→循环）
    """
    my_page_url = order_cfg.get("my_page_url", "")
    my_page_selector = order_cfg.get("my_page_selector", "a[href*='my']")
    order_count_selector = order_cfg.get("order_count_selector", ".order-count")
    wait_timeout = order_cfg.get("wait_timeout", 30000)
    refresh_interval = order_cfg.get("refresh_interval", 3)
    max_retries = order_cfg.get("max_retries", 999)
    up_goods_times = order_cfg.get("up_goods_times", "40")
    last_up_goods_time = datetime.datetime.now()

    print(f"[mania] ═══ 开始监控订单 ═══")
    print(f"[mania] 我的页面: {my_page_url}")
    print(f"[mania] 订单选择器: {order_count_selector}")
    print(f"[mania] 刷新间隔: {refresh_interval}s, 超时: {wait_timeout}ms, 最大重试: {max_retries}")

    has_credentials = bool(login_url and username and password and login_config)
    retry_count = 0

    def _is_stopped() -> bool:
        return stop_event is not None and stop_event.is_set()

    while retry_count < max_retries:
        if _is_stopped():
            print(f"[mania] 收到终止信号，退出重试循环")
            return {
                "status": "cancelled",
                "message": "用户手动终止",
                "order_count": 0,
                "duration_ms": int((time.time() - start) * 1000),
            }
        try:
            print(f"[mania] ─── 启动浏览器 (重试={retry_count}) ───")
            with sync_playwright() as p:
                is_captcha = (login_type == "captcha")
                browser, context, page = launch_browser(
                    p,
                    headless=False if is_captcha else PLAYWRIGHT_HEADLESS,
                    slow_mo=300 if (not PLAYWRIGHT_HEADLESS or is_captcha) else 0,
                    account_id=account_id,
                )

                # 自动处理 alert/confirm/prompt 弹窗，默认点击确定
                page.on("dialog", lambda dialog: dialog.accept())
                print(f"[mania] 浏览器已启动，dialog自动接受已注册")

                # ── 0. 登录 ──
                if has_credentials:
                    print(f"[mania] ─── 步骤0: 登录 ───")
                    login_result = _do_login(page, login_url, username, password, login_config,
                                             website_id, account_id, login_type,
                                             my_page_url=my_page_url, stop_event=stop_event)
                    if login_result["status"] != "success":
                        print(f"[mania] ❌ 登录失败: {login_result['message']}")
                        return {
                            "status": "failed",
                            "message": f"登录失败，无法查询订单：{login_result['message']}",
                            "order_count": 0,
                            "duration_ms": int((time.time() - start) * 1000),
                        }

                # ── 1. 进入“我的页面” ──
                print(f"[mania] ─── 步骤1: 进入我的页面 ───")
                if my_page_url:
                    print(f"[mania] 导航到: {my_page_url}")
                    try:
                        page.goto(my_page_url, wait_until="domcontentloaded", timeout=wait_timeout)
                    except Exception as e:
                        print(f"[mania] 进入我的页面超时: {e}，重试...")
                        try:
                            page.goto(my_page_url, wait_until="commit", timeout=wait_timeout)
                        except Exception as e2:
                            print(f"[mania] 进入我的页面二次尝试也失败: {e2}")
                            raise
                elif my_page_selector:
                    try:
                        page.wait_for_selector(my_page_selector, timeout=10000)
                        page.click(my_page_selector)
                        page.wait_for_load_state("networkidle", timeout=wait_timeout)
                    except Exception as e:
                        print(f"[mania] 点击我的页面链接超时: {e}")
                        raise
                else:
                    return {
                        "status": "failed",
                        "message": "未配置 my_page_url 或 my_page_selector",
                        "order_count": 0,
                        "duration_ms": int((time.time() - start) * 1000),
                    }

                # ── 2. 等待页面加载完毕 ──
                print(f"[mania] ─── 步骤2: 等待页面加载 ───")
                page.wait_for_timeout(1000)
                try:
                    page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    pass

                # 登录+进入页面成功，重置重试计数
                retry_count = 0
                print(f"[mania] ✅ 登录+进入页面成功，开始循环检测")
                print(f"[mania] 当前URL: {page.url}")

                # ── 3. 循环：刷新页面 → 检测订单数量 ──
                print(f"[mania] ─── 步骤3: 开始订单检测循环 ───")
                check_round = 0
                while True:
                    if _is_stopped():
                        print(f"[mania] 收到终止信号，退出监控循环")
                        try:
                            cookie_reader.save_from_context(context, account_id)
                        except Exception:
                            pass
                        try:
                            context.close()
                        except Exception:
                            pass
                        sync_upload_profile(account_id)
                        return {
                            "status": "cancelled",
                            "message": "用户手动终止",
                            "order_count": 0,
                            "duration_ms": int((time.time() - start) * 1000),
                        }
                    check_round += 1
                    try:
                        page.wait_for_selector(order_count_selector, timeout=10000)
                        count_text = page.text_content(order_count_selector) or "0"
                        numbers = re.findall(r'\d+', count_text)
                        order_count = int(numbers[0]) if numbers else 0
                    except Exception as e:
                        print(f"[mania] 第{check_round}轮查询元素失败: {e}，刷新页面后重试")
                        try:
                            page.reload(wait_until="domcontentloaded", timeout=wait_timeout)
                        except Exception as reload_err:
                            print(f"[mania] 刷新页面超时: {reload_err}，尝试重新导航到我的页面")
                            try:
                                page.goto(my_page_url, wait_until="domcontentloaded", timeout=wait_timeout)
                            except Exception:
                                raise  # 导航也失败，交给外层重试
                        page.wait_for_timeout(3000)
                        continue

                    if order_count > 0:
                        print(f"[mania] 第{check_round}轮: 检测到 {order_count} 个订单！播放提醒")
                        play_alert_audio(text=f"{account_id}号商铺检测到 {order_count} 个订单！")
                    else:
                        if check_round % 10 == 1:
                            print(f"[mania] 第{check_round}轮: 无订单，{refresh_interval}s后刷新 (URL: {page.url})")
                    #每up_goods_times（可能是字符串需要转化为数字）检测是否存在.cpnt.last，若存在则检查他下面的a标签，拿到href属性，拼到page.url后跳转
                    if (datetime.datetime.now() - last_up_goods_time).seconds > int(up_goods_times):

                        try:
                            page.wait_for_selector(".cpnt.last", timeout=1000)
                        except Exception as e:
                            pass
                        a_tag = page.query_selector(".cpnt.last a")
                        if a_tag:
                            href = a_tag.get_attribute("href")
                            if href:
                                print(f"[mania] 跳转链接: {href}")
                                try:
                                    page.goto(page.url+href, wait_until="domcontentloaded", timeout=wait_timeout)
                                except Exception as e:
                                    print(f"[mania] 跳转上架页面超时: {e}")
                                page.wait_for_timeout(1000)
                                try:
                                    page.wait_for_load_state("networkidle", timeout=15000)
                                except Exception:
                                    pass

                        #检查.g_blue_table.tb_list下的tbody下的tr标签的数量，若大于等于1则对最后一个tr标签下的.flex_box .reregist按钮点击
                        try:
                            page.wait_for_selector(".g_blue_table.tb_list tbody tr", timeout=2000)
                        except Exception as e:
                            pass
                        tr_tags = page.query_selector_all(".g_blue_table.tb_list tbody tr")
                        print(f"[mania] 上架商品数量: {len(tr_tags)}")
                        if len(tr_tags) >= 1:
                            last_tr = tr_tags[-1]
                            reregist_button = last_tr.query_selector(".flex_box .reregist")
                            if reregist_button:
                                print(f"[mania] 刷新上架商品: {last_tr.text_content()}")
                                last_up_goods_time = datetime.datetime.now()
                                reregist_button.click()

                    page.wait_for_timeout(refresh_interval * 1000)
                    try:
                        page.reload(wait_until="domcontentloaded", timeout=wait_timeout)
                    except Exception as e:
                        print(f"[mania] 循环刷新超时: {e}，尝试导航到我的页面")
                        try:
                            page.goto(my_page_url, wait_until="domcontentloaded", timeout=wait_timeout)
                        except Exception:
                            raise
                        page.wait_for_timeout(2000)

        except Exception as e:
            retry_count += 1
            print(f"[mania] 第{retry_count}次崩溃，5s后重新完整流程（登录→订单页→循环）: {e}")
            try:
                page.wait_for_timeout(5000)
            except Exception:
                time.sleep(5)
            # continue outer while loop → re-login

    return {
        "status": "failed",
        "message": f"重试{max_retries}次后仍然失败",
        "order_count": 0,
        "duration_ms": int((time.time() - start) * 1000),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# website_id == 3 (itembay) 的业务逻辑
# ═══════════════════════════════════════════════════════════════════════════════

def _check_website_3(
    order_cfg: dict,
    start: float,
    login_url: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    login_config: Optional[dict] = None,
    login_type: str = "form",
    stop_event: Optional[threading.Event] = None,
    account_id: Optional[int] = None,
    website_id: Optional[int] = None,
) -> dict:
    """
    持续循环监控订单：
    1. 自动登录 → 进入"我的页面"
    2. 循环刷新页面 → 检测订单数量 → 有单播放提醒
    3. 出现不可控异常 → 重新走完整流程（登录→我的页面→循环）
    """
    my_page_url = order_cfg.get("my_page_url", "https://www.itembay.com/mybay/status/mybayStatusSellList")
    my_page_selector = order_cfg.get("my_page_selector", "a[href*='my']")
    order_count_selector = order_cfg.get("order_count_selector", ".order-count")
    wait_timeout = order_cfg.get("wait_timeout", 30000)
    refresh_interval = order_cfg.get("refresh_interval", 3)
    max_retries = order_cfg.get("max_retries", 999)
    up_goods_times = order_cfg.get("up_goods_times", "40")
    last_up_goods_time = datetime.datetime.now()

    print(f"[itemBay] ═══ 开始监控订单 ═══")
    print(f"[itemBay] 我的页面: {my_page_url}")
    print(f"[itemBay] 订单选择器: {order_count_selector}, 刷新间隔: {refresh_interval}s")

    has_credentials = bool(login_url and username and password and login_config)
    retry_count = 0

    def _is_stopped() -> bool:
        return stop_event is not None and stop_event.is_set()

    while retry_count < max_retries:
        if _is_stopped():
            print(f"[itemBay] 收到终止信号，退出重试循环")
            return {
                "status": "cancelled",
                "message": "用户手动终止",
                "order_count": 0,
                "duration_ms": int((time.time() - start) * 1000),
            }
        try:
            print(f"[itemBay] ─── 启动浏览器 (重试={retry_count}) ───")
            with sync_playwright() as p:
                is_captcha = (login_type == "captcha")
                browser, context, page = launch_browser(
                    p,
                    headless=False if is_captcha else PLAYWRIGHT_HEADLESS,
                    slow_mo=300 if (not PLAYWRIGHT_HEADLESS or is_captcha) else 0,
                    account_id=account_id,
                )
                print(f"[itemBay] 浏览器已启动")

                # ── 0. 登录 ──
                if has_credentials:
                    print(f"[itemBay] ─── 步骤0: 登录 ───")
                    login_result = _do_login(page, login_url, username, password, login_config,
                                             website_id, account_id, login_type,
                                             my_page_url=my_page_url, stop_event=stop_event)
                    if login_result["status"] != "success":
                        print(f"[itemBay] ❌ 登录失败: {login_result['message']}")
                        raise Exception(f"登录失败: {login_result['message']}")

                # ── 1. 进入“我的页面” ──
                print(f"[itemBay] ─── 步骤1: 进入我的页面 ───")
                if my_page_url:
                    print(f"[itemBay] 导航到: {my_page_url}")
                    try:
                        page.goto(my_page_url, wait_until="domcontentloaded", timeout=wait_timeout)
                    except Exception as e:
                        print(f"[itemBay] 进入我的页面超时: {e}，重试...")
                        try:
                            page.goto(my_page_url, wait_until="commit", timeout=wait_timeout)
                        except Exception as e2:
                            print(f"[itemBay] 进入我的页面二次尝试也失败: {e2}")
                            raise
                elif my_page_selector:
                    try:
                        page.wait_for_selector(my_page_selector, timeout=10000)
                        page.click(my_page_selector)
                        page.wait_for_load_state("networkidle", timeout=wait_timeout)
                    except Exception as e:
                        print(f"[itemBay] 点击我的页面链接超时: {e}")
                        raise
                else:
                    raise Exception("itemBay未配置 my_page_url 或 my_page_selector")

                # ── 2. 等待页面加载完毕 ──
                print(f"[itemBay] ─── 步骤2: 等待页面加载 ───")
                page.wait_for_timeout(1000)
                try:
                    page.wait_for_load_state("networkidle", timeout=5000)
                except Exception:
                    pass

                # 登录+进入页面成功，重置重试计数
                retry_count = 0
                print(f"[itemBay] ✅ 登录+进入页面成功，开始循环检测")
                print(f"[itemBay] 当前URL: {page.url}")

                # ── 3. 循环：刷新页面 → 检测订单数量 ──
                print(f"[itemBay] ─── 步骤3: 开始订单检测循环 ───")
                check_round = 0
                # 注册dialog自动接受（带异常保护，防止偶发already handled崩溃）
                def _safe_accept_dialog(dialog):
                    try:
                        dialog.accept()
                    except Exception as e:
                        print(f"[itemBay] [DEBUG] dialog处理异常(忽略): {e}")
                page.on("dialog", _safe_accept_dialog)
                while True:
                    if _is_stopped():
                        print(f"[itemBay] 收到终止信号，退出监控循环")
                        try:
                            cookie_reader.save_from_context(context, account_id)
                        except Exception:
                            pass
                        try:
                            context.close()
                        except Exception:
                            pass
                        sync_upload_profile(account_id)
                        return {
                            "status": "cancelled",
                            "message": "用户手动终止",
                            "order_count": 0,
                            "duration_ms": int((time.time() - start) * 1000),
                        }
                    check_round += 1
                    try:
                        page.wait_for_selector("#New3", state="attached", timeout=5000)
                        count_text = page.query_selector("#New3 img")
                        if count_text:
                            print(f"[itemBay] 第{check_round}轮: 检测到订单！播放提醒")
                            play_alert_audio(text=f"{account_id}号商铺检测到订单！")
                        else:
                            if check_round % 10 == 1:
                                print(f"[itemBay] 第{check_round}轮: 无订单，{refresh_interval}s后刷新")
                    except Exception as e:
                        print(f"[itemBay] 第{check_round}轮查询元素失败: {e}，刷新页面后重试")
                        try:
                            page.goto(my_page_url, wait_until="domcontentloaded", timeout=wait_timeout)
                        except Exception as nav_err:
                            print(f"[itemBay] 恢复导航也超时: {nav_err}")
                            raise
                        page.wait_for_timeout(3000)
                        continue

                    # 每up_goods_times检测是否存在#NavigationPanel，查它下面第3个child，若第三个是a，拿到a的href属性后跳转
                    if (datetime.datetime.now() - last_up_goods_time).seconds > int(up_goods_times):
                        try:
                            page.wait_for_selector("#NavigationPanel", timeout=1000)
                        except Exception:
                            pass

                        # 检查#NavigationPanel的第三个child是否是a标签
                        third_child = page.query_selector("#NavigationPanel > :nth-child(3)")
                        if third_child:
                            tag_name = third_child.evaluate("el => el.tagName.toLowerCase()")
                            if tag_name == "a":
                                href = third_child.get_attribute("href")
                                if href:
                                    print(f"[itemBay] 跳转链接: {href}")
                                    try:
                                        page.goto(href, wait_until="domcontentloaded", timeout=wait_timeout)
                                    except Exception as e:
                                        print(f"[itemBay] 跳转上架页面超时: {e}")
                                    page.wait_for_timeout(1000)
                                    try:
                                        page.wait_for_load_state("networkidle", timeout=5000)
                                    except Exception:
                                        pass

                        # 检查#frmMybay .list_type下的tbody下的tr标签的数量
                        try:
                            page.wait_for_selector("#frmMybay .list_type tbody tr", timeout=2000)
                        except Exception:
                            pass

                        tr_tags = page.query_selector_all("#frmMybay .list_type tbody tr")
                        print(f"[itemBay] 商品数量: {len(tr_tags)}")
                        flag = False
                        # 若大于等于1则检查每个tr的class是否包含bg_01，找到最后一个不包含的进行刷新
                        if len(tr_tags) >= 1:
                            target_tr = None
                            for tr in tr_tags:
                                tr_class = tr.get_attribute("class") or ""
                                if "bg_01" not in tr_class:
                                    target_tr = tr
                            if target_tr:
                                reregist_button = target_tr.query_selector(".btn_pop01.type03")
                                if reregist_button:
                                    flag = True
                                    print(f"[itemBay] 刷新上架商品: {target_tr.text_content() or ''}")
                                    print(f"[itemBay] 刷新上架商品点击按钮: {reregist_button.get_attribute('title')}")
                                    last_up_goods_time = datetime.datetime.now()
                                    reregist_button.click()
                                    # 等待页面跳转完成
                                    page.wait_for_timeout(2000)
                                    try:
                                        page.wait_for_load_state("networkidle", timeout=10000)
                                    except Exception:
                                        pass
                                    try:
                                        print(f"[itemBay] [DEBUG] 等待#imgSubmitButton出现...")
                                        page.wait_for_selector("#imgSubmitButton", timeout=8000)
                                        page.wait_for_timeout(500)
                                        submit_btn = page.query_selector("#imgSubmitButton")
                                        if submit_btn:
                                            print(f"[itemBay] [DEBUG] 点击#imgSubmitButton")
                                            submit_btn.click()
                                            print(f"[itemBay] [DEBUG] #imgSubmitButton点击完成，等待页面稳定...")
                                            # submit_btn可能触发二次跳转，等导航完成，否则后续page.goto会ERR_ABORTED
                                            page.wait_for_timeout(2000)
                                            try:
                                                page.wait_for_load_state("networkidle", timeout=10000)
                                            except Exception:
                                                pass
                                    except Exception as e:
                                        print(f"[itemBay] [DEBUG] submit_btn处理异常: {e}")
                        if not flag:
                            redirect_url = None
                            # 拿#NavigationPanel的第一个是否是a标签，若是则拿a的href属性后跳转
                            first_child = page.query_selector("#NavigationPanel > :nth-child(1)")
                            if first_child:
                                tag_name = first_child.evaluate("el => el.tagName.toLowerCase()")
                                if tag_name == "a":
                                    href = first_child.get_attribute("href")
                                    if href:
                                        redirect_url = href
                                        print(f"[itemBay] 跳转链接(NavPanel第1个): {href}")
                            # 若不是则跳转固定地址
                            if not redirect_url:
                                redirect_url = "https://www.itembay.com/mybay/status/mybayStatusSellList?ItemSeq=1&tiDirection=0"
                                print(f"[itemBay] 跳转固定地址: {redirect_url}")

                            try:
                                page.goto(redirect_url, wait_until="domcontentloaded", timeout=wait_timeout)
                            except Exception as e:
                                print(f"[itemBay] 跳转固定地址超时: {e}")
                            page.wait_for_timeout(1000)
                            try:
                                page.wait_for_load_state("networkidle", timeout=5000)
                            except Exception:
                                pass

                            # 跳转后重新检查#frmMybay .list_type下的tbody下的tr标签的数量
                            try:
                                page.wait_for_selector("#frmMybay .list_type tbody tr", timeout=2000)
                            except Exception:
                                pass

                            tr_tags = page.query_selector_all("#frmMybay .list_type tbody tr")
                            print(f"[itemBay] 跳转后上架商品数量: {len(tr_tags)}")
                            if len(tr_tags) >= 1:
                                target_tr = None
                                for tr in tr_tags:
                                    tr_class = tr.get_attribute("class") or ""
                                    if "bg_01" not in tr_class:
                                        target_tr = tr
                                if target_tr:
                                    reregist_button = target_tr.query_selector(".btn_pop01.type03")
                                    if reregist_button:
                                        print(f"[itemBay] 刷新上架商品: {target_tr.text_content() or ''}")
                                        print(f"[itemBay] 刷新上架商品点击按钮: {reregist_button.get_attribute('title')}")
                                        last_up_goods_time = datetime.datetime.now()
                                        reregist_button.click()
                                        # 等待页面跳转完成
                                        page.wait_for_timeout(2000)
                                        try:
                                            page.wait_for_load_state("networkidle", timeout=10000)
                                        except Exception:
                                            pass
                                        try:
                                            print(f"[itemBay] [DEBUG] 等待#imgSubmitButton出现(跳转后)...")
                                            page.wait_for_selector("#imgSubmitButton", timeout=8000)
                                            page.wait_for_timeout(500)
                                            submit_btn = page.query_selector("#imgSubmitButton")
                                            if submit_btn:
                                                print(f"[itemBay] [DEBUG] 点击#imgSubmitButton(跳转后)")
                                                submit_btn.click()
                                                print(f"[itemBay] [DEBUG] #imgSubmitButton点击完成(跳转后)，等待页面稳定...")
                                                # submit_btn可能触发二次跳转，等导航完成
                                                page.wait_for_timeout(2000)
                                                try:
                                                    page.wait_for_load_state("networkidle", timeout=10000)
                                                except Exception:
                                                    pass
                                        except Exception as e:
                                            print(f"[itemBay] [DEBUG] submit_btn处理异常(跳转后): {e}")

                    page.wait_for_timeout(refresh_interval * 1000)
                    try:
                        page.goto("https://www.itembay.com/mybay/mybayMainView", wait_until="domcontentloaded", timeout=wait_timeout)
                    except Exception as e:
                        print(f"[itemBay] 循环导航超时: {e}，重试...")
                        try:
                            page.goto("https://www.itembay.com/mybay/mybayMainView", wait_until="commit", timeout=wait_timeout)
                        except Exception:
                            raise

        except Exception as e:
            retry_count += 1
            print(f"[itemBay] 第{retry_count}次崩溃，5s后重新完整流程（登录→订单页→循环）: {e}")
            try:
                page.wait_for_timeout(5000)
            except Exception:
                time.sleep(5)
            # continue outer while loop → re-login

    return {
        "status": "failed",
        "message": f"重试{max_retries}次后仍然失败",
        "order_count": 0,
        "duration_ms": int((time.time() - start) * 1000),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# website_id == 2 (barotem) 的业务逻辑
# ═══════════════════════════════════════════════════════════════════════════════

def _check_website_2(
    order_cfg: dict,
    start: float,
    login_url: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    login_config: Optional[dict] = None,
    login_type: str = "form",
    stop_event: Optional[threading.Event] = None,
    account_id: Optional[int] = None,
    website_id: Optional[int] = None,
) -> dict:
    """
    持续循环监控订单：
    1. 自动登录 → 进入"我的页面"
    2. 循环刷新页面 → 检测订单数量 → 有单播放提醒
    3. 出现不可控异常 → 重新走完整流程（登录→我的页面→循环）
    """
    my_page_url = order_cfg.get("my_page_url", "")
    my_page_selector = order_cfg.get("my_page_selector", "a[href*='my']")
    order_count_selector = order_cfg.get("order_count_selector", ".order-count")
    wait_timeout = order_cfg.get("wait_timeout", 30000)
    refresh_interval = order_cfg.get("refresh_interval", 3)
    max_retries = order_cfg.get("max_retries", 999)

    print(f"[arotem] ═══ 开始监控订单 ═══")
    print(f"[arotem] 我的页面: {my_page_url}")
    print(f"[arotem] 订单选择器: {order_count_selector}, 刷新间隔: {refresh_interval}s")

    has_credentials = bool(login_url and username and password and login_config)
    retry_count = 0

    def _is_stopped() -> bool:
        return stop_event is not None and stop_event.is_set()

    while retry_count < max_retries:
        if _is_stopped():
            print(f"[arotem] 收到终止信号，退出重试循环")
            return {
                "status": "cancelled",
                "message": "用户手动终止",
                "order_count": 0,
                "duration_ms": int((time.time() - start) * 1000),
            }
        try:
            print(f"[arotem] ─── 启动浏览器 (重试={retry_count}) ───")
            with sync_playwright() as p:
                is_captcha = (login_type == "captcha")
                browser, context, page = launch_browser(
                    p,
                    headless=False if is_captcha else PLAYWRIGHT_HEADLESS,
                    slow_mo=300 if (not PLAYWRIGHT_HEADLESS or is_captcha) else 0,
                    account_id=account_id,
                )
                print(f"[arotem] 浏览器已启动")

                # 自动处理 alert/confirm/prompt 弹窗，默认点击确定
                page.on("dialog", lambda dialog: dialog.accept())

                # ── 0. 登录 ──
                if has_credentials:
                    print(f"[arotem] ─── 步骤0: 登录 ───")
                    login_result = _do_login(page, login_url, username, password, login_config,
                                             website_id, account_id, login_type,
                                             my_page_url=my_page_url, stop_event=stop_event)
                    if login_result["status"] != "success":
                        print(f"[arotem] ❌ 登录失败: {login_result['message']}")
                        return {
                            "status": "failed",
                            "message": f"登录失败，无法查询订单：{login_result['message']}",
                            "order_count": 0,
                            "duration_ms": int((time.time() - start) * 1000),
                        }

                # ── 1. 进入“我的页面” ──
                print(f"[arotem] ─── 步骤1: 进入我的页面 ───")
                if my_page_url:
                    print(f"[arotem] 导航到: {my_page_url}")
                    try:
                        page.goto(my_page_url, wait_until="commit", timeout=wait_timeout)
                    except Exception as e:
                        print(f"[arotem] 进入我的页面超时: {e}，重试...")
                        try:
                            page.goto(my_page_url, wait_until="commit", timeout=wait_timeout)
                        except Exception as e2:
                            print(f"[arotem] 进入我的页面二次尝试也失败: {e2}")
                            raise
                elif my_page_selector:
                    try:
                        page.wait_for_selector(my_page_selector, timeout=10000)
                        page.click(my_page_selector)
                        page.wait_for_load_state("networkidle", timeout=wait_timeout)
                    except Exception as e:
                        print(f"[arotem] 点击我的页面链接超时: {e}")
                        raise
                else:
                    return {
                        "status": "failed",
                        "message": "未配置 my_page_url 或 my_page_selector",
                        "order_count": 0,
                        "duration_ms": int((time.time() - start) * 1000),
                    }

                # ── 2. 等待页面加载完毕 ──
                print(f"[arotem] ─── 步骤2: 等待页面加载 ───")
                page.wait_for_timeout(1000)
                try:
                    page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    pass

                # ── 2.1 检测登录提示弹窗：出现则说明未登录（arotem 不重定向，仅弹确认框）──
                need_login = False
                try:
                    alert_el = page.query_selector("div.common_alert_check")
                    if alert_el:
                        onclick = alert_el.get_attribute("onclick") or ""
                        if "/auth/login" in onclick:
                            need_login = True
                            print(f"[arotem] 检测到登录提示弹窗(common_alert_check → /auth/login)，需要重新登录")
                except Exception as e:
                    print(f"[arotem] 检测登录提示弹窗异常(忽略): {e}")

                if need_login:
                    if not has_credentials:
                        raise Exception("检测到未登录（登录提示弹窗），但未配置登录凭证")
                    print(f"[arotem] ─── 步骤2.2: 强制重新登录 ───")
                    login_result = _do_login(page, login_url, username, password, login_config,
                                             website_id, account_id, login_type,
                                             my_page_url=my_page_url, force_login=True,
                                             stop_event=stop_event)
                    if login_result["status"] != "success":
                        print(f"[arotem] ❌ 重新登录失败: {login_result['message']}")
                        raise Exception(f"重新登录失败: {login_result['message']}")
                    # 重新进入我的页面
                    print(f"[arotem] 重新登录成功，重新进入我的页面: {my_page_url}")
                    page.goto(my_page_url, wait_until="commit", timeout=wait_timeout)
                    page.wait_for_timeout(1000)
                    try:
                        page.wait_for_load_state("networkidle", timeout=15000)
                    except Exception:
                        pass

                # 登录+进入页面成功，重置重试计数
                retry_count = 0
                print(f"[arotem] ✅ 登录+进入页面成功，开始循环检测")
                print(f"[arotem] 当前URL: {page.url}")

                # ── 3. 循环：刷新页面 → 检测订单数量 ──
                print(f"[arotem] ─── 步骤3: 开始订单检测循环 ───")
                check_round = 0
                while True:
                    if _is_stopped():
                        print(f"[arotem] 收到终止信号，退出监控循环")
                        try:
                            cookie_reader.save_from_context(context, account_id)
                        except Exception:
                            pass
                        try:
                            context.close()
                        except Exception:
                            pass
                        sync_upload_profile(account_id)
                        return {
                            "status": "cancelled",
                            "message": "用户手动终止",
                            "order_count": 0,
                            "duration_ms": int((time.time() - start) * 1000),
                        }
                    check_round += 1
                    try:
                        page.wait_for_selector(order_count_selector, timeout=10000)
                        count_text = page.text_content(order_count_selector) or "0"
                        numbers = re.findall(r'\d+', count_text)
                        order_count = int(numbers[0]) if numbers else 0
                    except Exception as e:
                        print(f"[arotem] 第{check_round}轮查询元素失败: {e}，刷新页面后重试")
                        try:
                            page.reload(wait_until="domcontentloaded", timeout=wait_timeout)
                        except Exception as reload_err:
                            print(f"[arotem] 刷新页面超时: {reload_err}，尝试重新导航到我的页面")
                            try:
                                page.goto(my_page_url, wait_until="domcontentloaded", timeout=wait_timeout)
                            except Exception:
                                raise
                        page.wait_for_timeout(3000)
                        continue

                    if order_count > 0:
                        print(f"[arotem] 第{check_round}轮: 检测到 {order_count} 个订单！播放提醒")
                        play_alert_audio(text=f"{account_id}号商铺检测到 {order_count} 个订单！")
                    else:
                        if check_round % 10 == 1:
                            print(f"[arotem] 第{check_round}轮: 无订单，{refresh_interval}s后刷新")

                    page.wait_for_timeout(refresh_interval * 1000)
                    try:
                        page.reload(wait_until="domcontentloaded", timeout=wait_timeout)
                    except Exception as e:
                        print(f"[arotem] 循环刷新超时: {e}，尝试导航到我的页面")
                        try:
                            page.goto(my_page_url, wait_until="domcontentloaded", timeout=wait_timeout)
                        except Exception:
                            raise
                        page.wait_for_timeout(2000)

        except Exception as e:
            retry_count += 1
            print(f"[arotem] 第{retry_count}次崩溃，5s后重新完整流程（登录→订单页→循环）: {e}")
            try:
                page.wait_for_timeout(5000)
            except Exception:
                time.sleep(5)
            # continue outer while loop → re-login

    return {
        "status": "failed",
        "message": f"重试{max_retries}次后仍然失败",
        "order_count": 0,
        "duration_ms": int((time.time() - start) * 1000),
    }
