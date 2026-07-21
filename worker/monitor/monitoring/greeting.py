"""
招呼执行器：接收总控下发的招呼指令，通过浏览器发送并回馈结果。

流程：
  1. 接收 WS 下发的 greeting 消息
     {order_id, scripts: [{content, image_url?}, ...], chat_url, account_id}
  2. 直接调用统一的 chat.sender.send_web_chat() 发送
  3. 通过 Reporter 回报 greeting_result {order_id, success, message}
"""
import threading
import traceback

from common.reporter import Reporter


def handle_greeting(msg: dict, reporter: Reporter,
                    stop_event: threading.Event = None,
                    main_loop=None):
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
        _report(reporter, order_id, False, "招呼话术列表为空")
        return

    if not chat_url:
        _report(reporter, order_id, False, "缺少聊天页面地址")
        return

    if not account_id:
        _report(reporter, order_id, False, "缺少 account_id")
        return

    try:
        if stop_event and stop_event.is_set():
            _report(reporter, order_id, False, "招呼任务已被取消")
            return

        from monitor.chat.sender import send_web_chat
        result = send_web_chat(account_id, chat_url, scripts,
                               main_loop=main_loop, keep_open=True)
        _report(reporter, order_id, result.get("success", False),
                result.get("message", ""))

    except Exception as e:
        traceback.print_exc()
        _report(reporter, order_id, False, f"招呼执行异常: {e}")


def _report(reporter: Reporter, order_id, success, message):
    """通过 Reporter 回馈招呼结果到总控。"""
    try:
        reporter.report_greeting_result(order_id, success, message)
    except Exception as e:
        print(f"[Greeting] 回馈结果失败 order_id={order_id}: {e}")
