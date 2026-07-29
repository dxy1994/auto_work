"""Generic order chat command executor with legacy greeting compatibility."""

from __future__ import annotations

import threading
import traceback
from typing import Any

from common.reporter import Reporter


def normalize_chat_command(message: dict[str, Any]) -> dict[str, Any]:
    """Return the canonical chat command understood by the generic sender."""
    if message.get("type") == "greeting":
        order_id = message.get("order_id")
        return {
            **message,
            "request_id": f"legacy-greeting-{order_id}",
            "purpose": "greeting",
            "messages": list(message.get("scripts") or []),
            "target": {
                "url": message.get("chat_url", ""),
                "input_selector": "#write_chat",
                "send_selector": "#send_btn",
                "file_selector": "#attach_layer input[type=file]",
                "upload_auto_send": True,
                "order_no": message.get("source_order_no", ""),
            },
        }

    messages = message.get("messages")
    target = message.get("target")
    if not isinstance(messages, list) or not messages:
        raise ValueError("聊天消息列表为空")
    if not isinstance(target, dict):
        raise ValueError("聊天目标配置无效")
    request_id = str(message.get("request_id") or "").strip()
    if not request_id:
        raise ValueError("聊天指令缺少 request_id")
    return {
        **message,
        "request_id": request_id,
        "purpose": str(message.get("purpose") or "manual").strip().lower(),
        "messages": messages,
        "target": target,
    }


def handle_chat(
        message: dict,
        reporter: Reporter,
        stop_event: threading.Event | None = None,
        main_loop=None,
) -> None:
    """Execute a chat command in a worker thread and report its result."""
    try:
        command = normalize_chat_command(message)
    except Exception as exc:
        command = {
            "request_id": str(message.get("request_id") or "invalid-chat"),
            "order_id": message.get("order_id"),
            "purpose": str(message.get("purpose") or "manual"),
        }
        report_chat_result(
            reporter,
            command,
            {"success": False, "message": str(exc)},
        )
        return

    if not command.get("account_id"):
        report_chat_result(
            reporter,
            command,
            {"success": False, "message": "聊天指令缺少 account_id"},
        )
        return
    if stop_event and stop_event.is_set():
        report_chat_result(
            reporter,
            command,
            {"success": False, "message": "聊天任务已被取消"},
        )
        return

    try:
        from monitor.chat.sender import send_chat

        result = send_chat(
            command["account_id"],
            command["target"],
            command["messages"],
            main_loop=main_loop,
            keep_open=False,
            post_action=command.get("post_action"),
        )
    except Exception as exc:
        traceback.print_exc()
        result = {"success": False, "message": f"聊天执行异常: {exc}"}
    report_chat_result(reporter, command, result)


def report_chat_result(
        reporter: Reporter,
        command: dict,
        result: dict,
        *,
        log_tag: str = "Chat",
) -> None:
    order_id = command.get("order_id")
    success = bool(result.get("success"))
    message = str(result.get("message") or "")
    try:
        if command.get("purpose") == "greeting":
            reporter.report_greeting_result(order_id, success, message)
        else:
            reporter.report_chat_result(
                command.get("request_id"),
                order_id,
                success,
                message,
                command.get("purpose") or "manual",
                {
                    key: result[key]
                    for key in (
                        "chat_sent",
                        "chat_closed",
                        "delivery_confirmed",
                    )
                    if key in result
                },
            )
    except Exception as exc:
        print(
            f"[{log_tag}] 回馈聊天结果失败 "
            f"request_id={command.get('request_id')} order_id={order_id}: {exc}"
        )
