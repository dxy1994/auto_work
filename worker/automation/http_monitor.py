"""
HTTP 订单监控模块（无需启动浏览器）。

使用 cookie_reader 保存的 Cookie 直接发 HTTP 请求拉取页面，
解析 HTML 提取订单数量。比浏览器轮询轻量 10 倍以上。

支持三个站点：
  - website_id == 1: itemmania
  - website_id == 2: barotem
  - website_id == 3: itembay

典型用法:
    result = check_order(account_id=1, website_id=1)
    if result["status"] == "ok":
        print(f"当前订单: {result['order_count']}")
"""
import re
import time
from typing import Optional

import requests
from bs4 import BeautifulSoup

from automation.cookie_reader import load

# ── 请求超时 ──
REQUEST_TIMEOUT = 30

# ── 各站点的监控配置 ──
_SITE_CONFIG = {
    1: {  # itemmania
        "my_page_url": "https://www.itemmania.com/myroom/sell/sell_regist.html",
        "order_selector": "#nav_sub_sell > li:nth-child(2) > a > span:nth-child(2)",
        "login_url_keyword": "/login",
        "login_check": "redirect",  # 登录页会重定向
    },
    2: {  # barotem
        "my_page_url": "https://www.barotem.com/mypage",
        "order_selector": "body > main > div.mypage_container > nav > div > ul:nth-child(1) > li:nth-child(2) > a > span",
        "login_url_keyword": "/auth/login",
        "login_check": "html",  # 登录页有特定弹窗元素
    },
    3: {  # itembay
        "my_page_url": "https://www.itembay.com/mybay/status/mybayStatusSellList",
        "order_selector": "#nav_sub_sell > li:nth-child(1) > a > span:nth-child(2)",
        "login_url_keyword": "/login",
        "login_check": "redirect",
    },
}

# ── 可被识别为登录页的 URL 关键词 ──
_LOGIN_URL_KEYWORDS = ["/login", "/auth", "/signin", "/member/login"]


def check_order(
    account_id: int,
    website_id: int,
    custom_url: Optional[str] = None,
    custom_selector: Optional[str] = None,
) -> dict:
    """
    使用已保存的 Cookie 通过 HTTP 检测订单数量。

    参数:
        account_id:      账号ID
        website_id:      网站ID (1/2/3)
        custom_url:      自定义监控URL（不传则用内置配置）
        custom_selector: 自定义CSS选择器（不传则用内置配置）

    返回:
        {"status": "ok"|"expired"|"no_cookies"|"error",
         "order_count": int,
         "message": str,
         "duration_ms": int}
    """
    start = time.time()
    cfg = _SITE_CONFIG.get(website_id)
    if not cfg and not custom_url:
        return _result("error", 0, f"网站 {website_id} 未配置 HTTP 监控", start)

    my_page_url = custom_url or cfg["my_page_url"]
    order_selector = custom_selector or cfg["order_selector"]

    # ── 1. 加载 Cookie ──
    cookies = load(account_id)
    if not cookies:
        return _result("no_cookies", 0, f"账号 {account_id} 无已保存的 Cookie，请先通过浏览器登录一次", start)

    # ── 2. 发请求 ──
    try:
        session = requests.Session()
        resp = session.get(
            my_page_url,
            cookies=cookies,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
            },
        )

        if resp.status_code != 200:
            return _result("error", 0, f"HTTP {resp.status_code}", start)

        final_url = resp.url
        html = resp.text

    except requests.Timeout:
        return _result("error", 0, "请求超时", start)
    except Exception as e:
        return _result("error", 0, f"请求异常: {e}", start)

    # ── 3. 检测登录态是否过期 ──
    if _is_logged_out(website_id, cfg, final_url, html):
        return _result("expired", 0, "Cookie 已过期，需重新登录", start)

    # ── 4. 解析订单数量 ──
    try:
        soup = BeautifulSoup(html, "html.parser")
        el = soup.select_one(order_selector)
        if el:
            text = el.get_text(strip=True) or "0"
            numbers = re.findall(r"\d+", text)
            order_count = int(numbers[0]) if numbers else 0
            return _result("ok", order_count, f"检测到 {order_count} 个订单", start)
        else:
            return _result("error", 0,
                           f"未找到订单元素（选择器: {order_selector}），页面结构可能已变化", start)
    except Exception as e:
        return _result("error", 0, f"解析HTML失败: {e}", start)


def _is_logged_out(website_id: int, cfg: dict, final_url: str, html: str) -> bool:
    """检测是否被重定向到登录页或 Cookie 已过期。"""
    check_type = cfg.get("login_check", "redirect")

    if check_type == "redirect":
        # 检查 URL 是否包含登录关键词
        for kw in _LOGIN_URL_KEYWORDS:
            if kw in final_url.lower():
                return True
        # 检查 URL 是否仍匹配目标页面
        my_page_url = cfg["my_page_url"]
        if my_page_url not in final_url:
            return True

    elif check_type == "html":
        # barotem: 检查登录提示弹窗
        try:
            soup = BeautifulSoup(html, "html.parser")
            alert_el = soup.select_one("div.common_alert_check")
            if alert_el:
                onclick = alert_el.get("onclick") or ""
                if "/auth/login" in onclick:
                    return True
        except Exception:
            pass

    return False


def _result(status: str, order_count: int, message: str, start: float) -> dict:
    return {
        "status": status,
        "order_count": order_count,
        "message": message,
        "duration_ms": int((time.time() - start) * 1000),
    }
