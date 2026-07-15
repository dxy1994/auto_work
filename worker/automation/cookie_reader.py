"""
浏览器 Cookie 保存/加载模块。

从 Playwright 持久化上下文中提取 Cookie 保存为 JSON 文件，
供 http_monitor 等纯 HTTP 模块使用，无需启动浏览器。

Cookie JSON 保存在 user_data/{account_id}/cookies.json，
随 RustFS 同步一起跨机器共享。
"""
import json
import os
from typing import Optional

# ── 浏览器用户数据根目录（与 browser.py 保持一致）──
_USER_DATA_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "user_data")

COOKIES_FILENAME = "cookies.json"


def cookies_path(account_id: int) -> str:
    """获取 Cookie JSON 文件路径。"""
    return os.path.join(_USER_DATA_ROOT, str(account_id), COOKIES_FILENAME)


def save_from_context(context, account_id: int) -> bool:
    """
    从 Playwright BrowserContext 提取全部 Cookie 并保存为 JSON。
    应在 context.close() 之前调用。
    """
    try:
        cookies = context.cookies()
        path = cookies_path(account_id)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)
        print(f"[CookieReader] ✅ 保存 {len(cookies)} 个 Cookie → {path}")
        return True
    except Exception as e:
        err_msg = str(e)
        if "Event loop is closed" in err_msg or "already stopped" in err_msg:
            print(f"[CookieReader] ⚠️ 保存 Cookie 跳过（浏览器已关闭）")
        else:
            print(f"[CookieReader] ❌ 保存 Cookie 失败: {e}")
        return False


def load(account_id: int) -> dict:
    """
    加载保存的 Cookie，转为 requests 可用的 {name: value} 字典。
    未保存则返回空 dict。
    """
    path = cookies_path(account_id)
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            cookies = json.load(f)
        return {c["name"]: c["value"] for c in cookies}
    except Exception as e:
        print(f"[CookieReader] ⚠️ 读取 Cookie 失败: {e}")
        return {}


def load_raw(account_id: int) -> Optional[list]:
    """加载原始 Cookie 列表（含 domain/path/expires 等字段）。"""
    path = cookies_path(account_id)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def has_cookies(account_id: int) -> bool:
    """是否已有保存的 Cookie。"""
    return os.path.isfile(cookies_path(account_id))
