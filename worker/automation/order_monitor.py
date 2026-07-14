"""
订单查询与提醒服务（worker 端）

根据 website_id 分发到不同站点的监控逻辑：
  - 1: itemmania
  - 2: barotem
  - 3: itembay

通用监控流程（_generic_monitor）统一处理：浏览器启动 → 登录 → 导航 → 轮询检测 → 异常重试。
各站点仅需提供：订单检测回调 + 上架刷新回调 + 可选的登录后检查回调。
"""
import datetime
import re
import threading
import time
from typing import Optional, Callable, Tuple

from patchright.sync_api import sync_playwright

import config
from automation.audio_alert import play_alert_audio
from automation.browser import launch_browser, sync_upload_profile
from automation.login_handler import do_login
from automation.cookie_reader import save_from_context

PLAYWRIGHT_HEADLESS = config.PLAYWRIGHT_HEADLESS


# ═══════════════════════════════════════════════════════════
# 通用辅助函数
# ═══════════════════════════════════════════════════════════

def _make_result(status, message, start, order_count=0):
    return {
        "status": status,
        "message": message,
        "order_count": order_count,
        "duration_ms": int((time.time() - start) * 1000),
    }


def _launch_monitor_browser(p, login_type, account_id, tag):
    """启动监控用浏览器，返回 (browser, context, page)。"""
    is_captcha = (login_type == "captcha")
    browser, context, page = launch_browser(
        p,
        headless=False if is_captcha else PLAYWRIGHT_HEADLESS,
        slow_mo=300 if (not PLAYWRIGHT_HEADLESS or is_captcha) else 0,
        account_id=account_id,
    )
    def _safe_accept(dialog):
        try:
            dialog.accept()
        except Exception:
            pass
    page.on("dialog", _safe_accept)
    print(f"[{tag}] 浏览器已启动")
    return browser, context, page


def _navigate_to_my_page(page, my_page_url, my_page_selector, wait_timeout, tag):
    """导航到"我的页面"，成功返回 True，失败抛出异常。"""
    if my_page_url:
        print(f"[{tag}] 导航到: {my_page_url}")
        try:
            page.goto(my_page_url, wait_until="domcontentloaded", timeout=wait_timeout)
        except Exception as e:
            print(f"[{tag}] 进入我的页面超时: {e}，重试...")
            try:
                page.goto(my_page_url, wait_until="commit", timeout=wait_timeout)
            except Exception as e2:
                print(f"[{tag}] 二次尝试也失败: {e2}")
                raise
    elif my_page_selector:
        page.wait_for_selector(my_page_selector, timeout=10000)
        page.click(my_page_selector)
        page.wait_for_load_state("networkidle", timeout=wait_timeout)
    else:
        raise Exception(f"[{tag}] 未配置 my_page_url 或 my_page_selector")


def _resolve_my_page(context, page, my_page_url, my_page_selector, wait_timeout, tag):
    """
    优先复用恢复的标签页，避免不必要的导航。
    1. 当前 page.url 已是目标 → 直接返回
    2. 从 context.pages 中查找匹配的页面 → 返回该页
    3. 都找不到 → 导航到目标页
    返回正确的 page（可能是 context.pages 中的另一个页面）。
    """
    # URL 模式：尝试复用恢复的标签页
    if my_page_url:
        # 1. 当前页面已经是目标
        if page.url == my_page_url:
            print(f"[{tag}] 当前页面已是目标页，无需导航")
            return page
        # 2. 从其他标签页中找
        for p in context.pages:
            if p != page and p.url == my_page_url:
                print(f"[{tag}] 从恢复标签页中找到目标页: {p.url}")
                return p
        # 3. 找不到 → 导航
        _navigate_to_my_page(page, my_page_url, "", wait_timeout, tag)
        return page

    # 选择器模式：无法预判目标 URL，直接导航
    _navigate_to_my_page(page, "", my_page_selector, wait_timeout, tag)
    return page


def _wait_page_stable(page, timeout=15000):
    """等待页面稳定（networkidle + 短暂缓冲）。"""
    page.wait_for_timeout(1000)
    try:
        page.wait_for_load_state("networkidle", timeout=timeout)
    except Exception:
        pass


def _save_and_upload(context, account_id):
    """保存 Cookie 并上传浏览器配置到 RustFS。"""
    try:
        save_from_context(context, account_id)
    except Exception:
        pass
    try:
        context.close()
    except Exception:
        pass
    sync_upload_profile(account_id)


def _safe_reload_or_navigate(page, my_page_url, wait_timeout, tag):
    """尝试刷新页面，失败则重新导航到我的页面。"""
    try:
        page.reload(wait_until="domcontentloaded", timeout=wait_timeout)
    except Exception as e:
        print(f"[{tag}] 刷新超时: {e}，重新导航")
        page.goto(my_page_url, wait_until="domcontentloaded", timeout=wait_timeout)
        page.wait_for_timeout(2000)


def _default_check_login_status(page, login_url, tag):
    """默认登录状态检查：检测当前URL是否被重定向到登录页。
    若当前页面 URL 前缀匹配登录页地址 → 登录已失效，返回 False。
    """
    if not login_url:
        return True
    current_url = page.url
    if current_url.startswith(login_url):
        print(f"[{tag}] ⚠️ 登录失效，当前在登录页: {current_url}")
        return False
    return True


# ═══════════════════════════════════════════════════════════
# 通用订单监控循环
# ═══════════════════════════════════════════════════════════

def _generic_monitor(
    tag: str,
    order_cfg: dict,
    start: float,
    account_id: int,
    website_id: int,
    login_url: Optional[str],
    username: Optional[str],
    password: Optional[str],
    login_config: dict,
    login_type: str,
    stop_event: Optional[threading.Event],
    detect_order: Callable,
    refresh_goods: Optional[Callable] = None,
    post_login_check: Optional[Callable] = None,
    check_login_status: Optional[Callable] = _default_check_login_status,
) -> dict:
    """
    通用订单监控循环。

    回调签名：
      detect_order(page) -> (detected: bool, count: int, alert_text: str)
        detected=True 表示检测到订单，触发音频提醒
      refresh_goods(page, last_time, timeout, tag) -> datetime.datetime
        返回更新后的 last_up_goods_time
      post_login_check(page) -> bool
        返回 True 表示需要重新登录（如 barotem 的登录弹窗检测）
      check_login_status(page, login_url, tag) -> bool
        每轮检测前检查登录状态，返回 False 表示登录失效需重新登录。
        默认为 _default_check_login_status（检测当前 URL 是否匹配登录页地址前缀）。
    """
    my_page_url = order_cfg.get("my_page_url", "")
    my_page_selector = order_cfg.get("my_page_selector", "")
    wait_timeout = order_cfg.get("wait_timeout", 30000)
    refresh_interval = order_cfg.get("refresh_interval", 3)
    max_retries = order_cfg.get("max_retries", 999)

    has_credentials = bool(login_url and username and password and login_config)
    retry_count = 0

    def _stopped():
        return stop_event is not None and stop_event.is_set()

    def _relogin():
        """重新登录并导航到我的页面。"""
        lr = do_login(
            page, login_url, username, password, login_config,
            website_id, account_id, login_type,
            my_page_url=my_page_url, force_login=True,
            stop_event=stop_event,
        )
        if lr["status"] != "success":
            raise Exception(f"重新登录失败: {lr['message']}")
        page.goto(my_page_url, wait_until="commit", timeout=wait_timeout)
        _wait_page_stable(page)

    print(f"[{tag}] ═══ 开始监控订单 ═══")
    print(f"[{tag}] 我的页面: {my_page_url}, 刷新间隔: {refresh_interval}s")

    while retry_count < max_retries:
        if _stopped():
            return _make_result("cancelled", "用户手动终止", start)

        try:
            print(f"[{tag}] ─── 启动浏览器 (重试={retry_count}) ───")
            with sync_playwright() as p:
                browser, context, page = _launch_monitor_browser(
                    p, login_type, account_id, tag)

                # ── 登录 ──
                if has_credentials:
                    print(f"[{tag}] ─── 步骤0: 登录 ───")
                    lr = do_login(
                        page, login_url, username, password, login_config,
                        website_id, account_id, login_type,
                        my_page_url=my_page_url, stop_event=stop_event,
                    )
                    if lr["status"] != "success":
                        print(f"[{tag}] ❌ 登录失败: {lr['message']}")
                        raise Exception(f"登录失败: {lr['message']}")

                # ── 登录后站点特有检查（如 barotem 登录弹窗）──
                did_relogin = False
                if post_login_check:
                    need_relogin = post_login_check(page)
                    if need_relogin:
                        if not has_credentials:
                            raise Exception("检测到未登录，但未配置登录凭证")
                        print(f"[{tag}] ── 强制重新登录 ──")
                        _relogin()
                        did_relogin = True

                # ── 进入"我的页面"（_relogin 已导航则跳过）──
                if not did_relogin:
                    print(f"[{tag}] ─── 步骤1: 进入我的页面 ───")
                    page = _resolve_my_page(context, page, my_page_url,
                                            my_page_selector, wait_timeout, tag)
                    # ── 等待页面稳定 ──
                    print(f"[{tag}] ─── 步骤2: 等待页面加载 ───")
                    _wait_page_stable(page)

                retry_count = 0
                print(f"[{tag}] ✅ 登录+进入页面成功，开始循环检测 "
                      f"(URL: {page.url})")

                # ── 轮询检测循环 ──
                print(f"[{tag}] ─── 步骤3: 开始订单检测循环 ───")
                check_round = 0
                last_up_goods_time = datetime.datetime.now()

                while True:
                    if _stopped():
                        print(f"[{tag}] 收到终止信号")
                        _save_and_upload(context, account_id)
                        return _make_result("cancelled", "用户手动终止", start)

                    check_round += 1

                    # ── 每次检测前检查登录状态 ──
                    if check_login_status and has_credentials:
                        try:
                            if not check_login_status(page, login_url, tag):
                                print(f"[{tag}] ── 检测到登录失效，重新登录 ──")
                                _relogin()
                        except Exception as e:
                            print(f"[{tag}] 登录状态检查异常，触发整体重试: {e}")
                            raise

                    # 检测订单
                    try:
                        detected, count, alert_text = detect_order(page)
                    except Exception as e:
                        print(f"[{tag}] 第{check_round}轮检测失败: {e}，"
                              f"刷新后重试")
                        _safe_reload_or_navigate(
                            page, my_page_url, wait_timeout, tag)
                        page.wait_for_timeout(3000)
                        continue

                    if detected:
                        print(f"[{tag}] 第{check_round}轮: {alert_text}")
                        play_alert_audio(text=alert_text)
                    elif check_round % 10 == 1:
                        print(f"[{tag}] 第{check_round}轮: 无订单，"
                              f"{refresh_interval}s后刷新")

                    # 上架刷新
                    if refresh_goods:
                        last_up_goods_time = refresh_goods(
                            page, last_up_goods_time, wait_timeout, tag)

                    # 等待 + 刷新页面
                    page.wait_for_timeout(refresh_interval * 1000)
                    _safe_reload_or_navigate(
                        page, my_page_url, wait_timeout, tag)

        except Exception as e:
            retry_count += 1
            print(f"[{tag}] 第{retry_count}次崩溃，5s后重试: {e}")
            # ── 异常时确保持久化上下文数据刷盘，下次启动才能复用登录态 ──
            try:
                save_from_context(context, account_id)
            except Exception:
                pass
            try:
                context.close()
            except Exception:
                pass
            try:
                if browser:
                    browser.close()
            except Exception:
                pass
            time.sleep(5)

    return _make_result("failed", f"重试{max_retries}次后仍然失败", start)


# ═══════════════════════════════════════════════════════════
# 站点订单检测回调
# ═══════════════════════════════════════════════════════════

def _detect_itemmania(page) -> Tuple[bool, int, str]:
    sel = "#nav_sub_sell > li:nth-child(2) > a > span:nth-child(2)"
    page.wait_for_selector(sel, timeout=10000)
    text = page.text_content(sel) or "0"
    nums = re.findall(r'\d+', text)
    count = int(nums[0]) if nums else 0
    return (count > 0, count, f"检测到 {count} 个订单！")


def _detect_barotem(page) -> Tuple[bool, int, str]:
    sel = ("body > main > div.mypage_container > nav > div > "
           "ul:nth-child(1) > li:nth-child(2) > a > span")
    page.wait_for_selector(sel, timeout=10000)
    text = page.text_content(sel) or "0"
    nums = re.findall(r'\d+', text)
    count = int(nums[0]) if nums else 0
    return (count > 0, count, f"检测到 {count} 个订单！")


def _detect_itembay(page) -> Tuple[bool, int, str]:
    page.wait_for_selector("#New3", state="attached", timeout=5000)
    img = page.query_selector("#New3 img")
    has_order = img is not None
    return (has_order, 1 if has_order else 0, "检测到订单！" if has_order else "")


# ═══════════════════════════════════════════════════════════
# 站点上架刷新回调
# ═══════════════════════════════════════════════════════════

def _refresh_goods_itemmania(
    page, last_time: datetime.datetime, timeout: int, tag: str,
) -> datetime.datetime:
    interval = 40
    if (datetime.datetime.now() - last_time).seconds <= interval:
        return last_time

    # 跳转到上架页面
    try:
        page.wait_for_selector(".cpnt.last", timeout=1000)
    except Exception:
        pass
    a_tag = page.query_selector(".cpnt.last a")
    if a_tag:
        href = a_tag.get_attribute("href")
        if href:
            print(f"[{tag}] 跳转上架页面: {href}")
            try:
                page.goto(page.url + href, wait_until="domcontentloaded",
                          timeout=timeout)
            except Exception as e:
                print(f"[{tag}] 跳转上架页面超时: {e}")
            page.wait_for_timeout(1000)
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass

    # 检查上架商品并刷新
    try:
        page.wait_for_selector(".g_blue_table.tb_list tbody tr", timeout=2000)
    except Exception:
        pass
    trs = page.query_selector_all(".g_blue_table.tb_list tbody tr")
    print(f"[{tag}] 上架商品数量: {len(trs)}")
    if len(trs) >= 1:
        btn = trs[-1].query_selector(".flex_box .reregist")
        if btn:
            print(f"[{tag}] 刷新上架商品: {trs[-1].text_content()}")
            last_time = datetime.datetime.now()
            btn.click()
    return last_time


def _refresh_goods_itembay(
    page, last_time: datetime.datetime, timeout: int, tag: str,
) -> datetime.datetime:
    interval = 40
    if (datetime.datetime.now() - last_time).seconds <= interval:
        return last_time

    # 导航到上架管理面板
    try:
        page.wait_for_selector("#NavigationPanel", timeout=1000)
    except Exception:
        pass

    # 检查第3个child是否是a标签，跳转
    third = page.query_selector("#NavigationPanel > :nth-child(3)")
    if third:
        tn = third.evaluate("el => el.tagName.toLowerCase()")
        if tn == "a":
            href = third.get_attribute("href")
            if href:
                print(f"[{tag}] 跳转上架页面: {href}")
                try:
                    page.goto(href, wait_until="domcontentloaded",
                              timeout=timeout)
                except Exception as e:
                    print(f"[{tag}] 跳转上架页面超时: {e}")
                page.wait_for_timeout(1000)
                try:
                    page.wait_for_load_state("networkidle", timeout=5000)
                except Exception:
                    pass

    # 查找并刷新商品
    return _itembay_find_and_refresh(page, last_time, timeout, tag)


def _itembay_find_and_refresh(
    page, last_time: datetime.datetime, timeout: int, tag: str,
) -> datetime.datetime:
    """在 itembay 上架列表页查找可刷新的商品并点击重新上架按钮。"""
    try:
        page.wait_for_selector("#frmMybay .list_type tbody tr", timeout=2000)
    except Exception:
        pass

    trs = page.query_selector_all("#frmMybay .list_type tbody tr")
    print(f"[{tag}] 商品数量: {len(trs)}")

    target_tr = None
    for tr in trs:
        cls = tr.get_attribute("class") or ""
        if "bg_01" not in cls:
            target_tr = tr

    if not target_tr:
        # 没有可刷新的商品，尝试跳转备选页面
        redirect_url = None
        first = page.query_selector("#NavigationPanel > :nth-child(1)")
        if first:
            tn = first.evaluate("el => el.tagName.toLowerCase()")
            if tn == "a":
                href = first.get_attribute("href")
                if href:
                    redirect_url = href
                    print(f"[{tag}] 跳转NavPanel第1个: {href}")
        if not redirect_url:
            redirect_url = ("https://www.itembay.com/mybay/status/"
                            "mybayStatusSellList?ItemSeq=1&tiDirection=0")
            print(f"[{tag}] 跳转固定地址: {redirect_url}")
        try:
            page.goto(redirect_url, wait_until="domcontentloaded",
                      timeout=timeout)
        except Exception as e:
            print(f"[{tag}] 跳转固定地址超时: {e}")
        page.wait_for_timeout(1000)
        try:
            page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass

        # 跳转后再次检查
        try:
            page.wait_for_selector("#frmMybay .list_type tbody tr",
                                   timeout=2000)
        except Exception:
            pass
        trs = page.query_selector_all("#frmMybay .list_type tbody tr")
        print(f"[{tag}] 跳转后商品数量: {len(trs)}")
        for tr in trs:
            cls = tr.get_attribute("class") or ""
            if "bg_01" not in cls:
                target_tr = tr
                break

    if target_tr:
        btn = target_tr.query_selector(".btn_pop01.type03")
        if btn:
            print(f"[{tag}] 刷新上架: {target_tr.text_content() or ''}")
            last_time = datetime.datetime.now()
            btn.click()
            page.wait_for_timeout(2000)
            try:
                page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass
            # 等待并点击二次确认按钮
            try:
                page.wait_for_selector("#imgSubmitButton", timeout=8000)
                page.wait_for_timeout(500)
                submit = page.query_selector("#imgSubmitButton")
                if submit:
                    print(f"[{tag}] 点击确认按钮")
                    submit.click()
                    page.wait_for_timeout(2000)
                    try:
                        page.wait_for_load_state("networkidle", timeout=10000)
                    except Exception:
                        pass
            except Exception as e:
                print(f"[{tag}] 确认按钮处理异常: {e}")
    return last_time


# ═══════════════════════════════════════════════════════════
# barotem 登录后弹窗检测
# ═══════════════════════════════════════════════════════════

def _barotem_post_login_check(page) -> bool:
    """检测 barotem 登录提示弹窗，返回 True 表示需要重新登录。"""
    try:
        alert_el = page.query_selector("div.common_alert_check")
        if alert_el:
            onclick = alert_el.get_attribute("onclick") or ""
            if "/auth/login" in onclick:
                print("[arotem] 检测到登录弹窗，需重新登录")
                return True
    except Exception:
        pass
    return False


def _barotem_check_login_status(page, login_url, tag):
    """barotem 登录状态检查：URL检查 + 登录弹窗检查。"""
    if not _default_check_login_status(page, login_url, tag):
        return False
    # 额外检查登录弹窗（即使 URL 未变化，弹窗也可能出现）
    try:
        alert_el = page.query_selector("div.common_alert_check")
        if alert_el:
            onclick = alert_el.get_attribute("onclick") or ""
            if "/auth/login" in onclick:
                print(f"[{tag}] ⚠️ 检测到登录弹窗，需要重新登录")
                return False
    except Exception:
        pass
    return True


# ═══════════════════════════════════════════════════════════
# 业务逻辑分发
# ═══════════════════════════════════════════════════════════

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
    """根据 website_id 分发到不同站点的监控逻辑。"""
    start = time.time()
    login_config = login_config or {}

    cred_status = "有" if url and username and password else "无"
    print(f"[OrderCheck] ═══ 开始订单检查 ═══")
    print(f"[OrderCheck] 账号ID={account_id}, 网站ID={website_id}, "
          f"登录类型={login_type}, 凭证={cred_status}")

    result = None
    try:
        common = dict(
            start=start, account_id=account_id, website_id=website_id,
            login_url=url, username=username, password=password,
            login_config=login_config, login_type=login_type,
            stop_event=stop_event,
        )

        if website_id == 1:
            result = _check_website_1(**common)
        elif website_id == 2:
            result = _check_website_2(**common)
        elif website_id == 3:
            result = _check_website_3(**common)
        else:
            result = _make_result(
                "skipped", f"网站 ID {website_id} 未配置订单查询逻辑", start)
    except Exception as e:
        result = _make_result("failed", f"订单查询异常：{e}", start)
    finally:
        status = result.get("status", "unknown") if result else "no_result"
        msg = result.get("message", "") if result else ""
        elapsed = int((time.time() - start) * 1000)
        print(f"[OrderCheck] ═══ 订单检查结束 ═══ "
              f"账号ID={account_id}, 状态={status}, 耗时={elapsed}ms, {msg}")
    return result


# ═══════════════════════════════════════════════════════════
# 各站点入口（仅配置差异，委托 _generic_monitor）
# ═══════════════════════════════════════════════════════════

def _check_website_1(**kw) -> dict:
    """itemmania 监控"""
    order_cfg = {
        "my_page_url": "https://www.itemmania.com/myroom/sell/sell_regist.html",
        "my_page_selector": "#g_BODY > header > div > div.header-nav-wrapper > nav > a:nth-child(4)",
        "wait_timeout": 10000,
        "refresh_interval": 3,
        "max_retries": 999,
    }
    return _generic_monitor(
        tag="mania", order_cfg=order_cfg,
        detect_order=_detect_itemmania,
        refresh_goods=_refresh_goods_itemmania,
        **kw,
    )


def _check_website_2(**kw) -> dict:
    """barotem 监控"""
    order_cfg = {
        "my_page_url": "https://www.barotem.com/mypage",
        "my_page_selector": "",
        "wait_timeout": 10000,
        "refresh_interval": 3,
        "max_retries": 999,
    }
    return _generic_monitor(
        tag="arotem", order_cfg=order_cfg,
        detect_order=_detect_barotem,
        post_login_check=_barotem_post_login_check,
        check_login_status=_barotem_check_login_status,
        **kw,
    )


def _check_website_3(**kw) -> dict:
    """itembay 监控"""
    order_cfg = {
        "my_page_url": "https://www.itembay.com/mybay/status/mybayStatusSellList",
        "my_page_selector": "",
        "wait_timeout": 10000,
        "refresh_interval": 3,
        "max_retries": 999,
    }
    return _generic_monitor(
        tag="itemBay", order_cfg=order_cfg,
        detect_order=_detect_itembay,
        refresh_goods=_refresh_goods_itembay,
        **kw,
    )
