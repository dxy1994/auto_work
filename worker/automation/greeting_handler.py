"""
招呼执行器：接收总控下发的招呼指令，通过浏览器发送并回馈结果。

流程：
  1. 接收 WS 下发的 greeting 消息
     {order_id, scripts: [{content, image_url?}, ...], chat_url, account_id}
  2. 从 chat_url 域名推导 website_id，路由到对应站点模块
  3. 通过浏览器打开聊天页面，逐条发送图文
  4. 通过 Reporter 回报 greeting_result {order_id, success, message}
"""
import threading
import traceback

from reporter import get_reporter

# ── 域名 → website_id 映射 ──
_DOMAIN_WEBSITE_MAP = {
    "itemmania.com": 1,
    "barotem.com": 2,
    "itembay.com": 3,
}


def _extract_website_id(chat_url: str) -> int:
    """从聊天页面 URL 的域名推导 website_id。"""
    for domain, wid in _DOMAIN_WEBSITE_MAP.items():
        if domain in chat_url:
            return wid
    return 0


def handle_greeting(msg: dict, stop_event: threading.Event = None):
    """
    在线程中执行招呼，完成后自动回馈总控。

    msg 包含:
      - order_id: int             订单 ID
      - scripts: list[dict]       话术列表，每项 {content?, image_url?}
      - chat_url: str             聊天页面 URL
      - account_id: int           账号 ID（定位浏览器会话）
    """
    order_id = msg.get("order_id")
    scripts = msg.get("scripts", [])
    chat_url = msg.get("chat_url", "")
    account_id = msg.get("account_id")

    if not scripts:
        _report(order_id, False, "招呼话术列表为空")
        return

    if not chat_url:
        _report(order_id, False, "缺少聊天页面地址")
        return

    if not account_id:
        _report(order_id, False, "缺少 account_id")
        return

    try:
        if stop_event and stop_event.is_set():
            _report(order_id, False, "招呼任务已被取消")
            return

        _do_greeting(order_id, account_id, chat_url, scripts)

    except Exception as e:
        traceback.print_exc()
        _report(order_id, False, f"招呼执行异常: {e}")


def _do_greeting(order_id: int, account_id: int, chat_url: str, scripts: list):
    """根据 website_id 路由到对应站点的聊天发送器。"""
    website_id = _extract_website_id(chat_url)
    if website_id == 0:
        _report(order_id, False, f"无法识别聊天 URL 对应的网站: {chat_url}")
        return

    from automation.monitors import MONITOR_REGISTRY
    monitor_cls = MONITOR_REGISTRY.get(website_id)
    if monitor_cls is None:
        _report(order_id, False, f"网站 ID {website_id} 未注册")
        return

    # 从 Monitor 所在模块获取 send_web_chat 函数
    import importlib
    module = importlib.import_module(monitor_cls.__module__)
    send_web_chat = getattr(module, 'send_web_chat', None)
    if send_web_chat is None:
        _report(order_id, False, f"网站 ID {website_id} 未实现聊天发送功能")
        return

    result = send_web_chat(account_id, chat_url, scripts)
    _report(order_id, result.get("success", False),
            result.get("message", ""))


def _report(order_id, success, message):
    """通过 Reporter 回馈招呼结果到总控。"""
    try:
        reporter = get_reporter()
        reporter.report_greeting_result(order_id, success, message)
    except RuntimeError:
        print(f"[Greeting] Reporter 未初始化，无法回馈结果 order_id={order_id}")
    except Exception as e:
        print(f"[Greeting] 回馈结果失败 order_id={order_id}: {e}")
