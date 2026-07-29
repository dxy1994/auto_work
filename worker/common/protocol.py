"""WebSocket 消息协议常量与构造方法。

集中管理所有中控 ↔ Worker 的消息类型和格式，
避免在 main.py 中散落裸 dict 构造。
"""
from typing import Optional


# ═══════════════════════════════════════════════════════════
# 消息类型常量
# ═══════════════════════════════════════════════════════════

# Worker → 中控
TYPE_REGISTER = "register"
TYPE_HEARTBEAT = "heartbeat"
TYPE_TASK_STATUS = "task_status"
TYPE_TASK_RESULT = "task_result"
TYPE_TASK_EVENT = "task_event"
TYPE_CHECK_ORDERS = "check_orders"
TYPE_ORDER_DETECTED = "order_detected"
TYPE_TRADE_OFFER_DECISION = "trade_offer_decision"
TYPE_TRADE_STATUS = "trade_status"
TYPE_TRADE_BUYER_REVIEW = "trade_buyer_review"
TYPE_TRADE_GAME_SCREENSHOT = "trade_game_screenshot"
TYPE_GREETING_RESULT = "greeting_result"
TYPE_CHAT_RESULT = "chat_result"

# 中控 → Worker
TYPE_REGISTERED = "registered"
TYPE_ORDER_CHECK = "order_check"
TYPE_CANCEL = "cancel"
TYPE_ORDERS_CHECK_RESULT = "orders_check_result"
TYPE_GREETING = "greeting"
TYPE_CHAT = "chat"
TYPE_TRADE_OFFER = "trade_offer"
TYPE_TRADE_START = "trade_start"
TYPE_TRADE_CANCEL = "trade_cancel"
TYPE_TRADE_BUYER_REVIEW_DECISION = "trade_buyer_review_decision"
TYPE_TRADE_GAME_SCREENSHOT_SAVED = "trade_game_screenshot_saved"


# ═══════════════════════════════════════════════════════════
# 消息构造（Worker → 中控）
# ═══════════════════════════════════════════════════════════

def register_msg(machine_info: dict) -> dict:
    return {"type": TYPE_REGISTER, **machine_info}


def heartbeat_msg(runtime: dict) -> dict:
    return {"type": TYPE_HEARTBEAT, "runtime": runtime}


def task_status_msg(task_id: str, status: str, message: str = "",
                    account_id: Optional[int] = None) -> dict:
    return {
        "type": TYPE_TASK_STATUS,
        "task_id": task_id,
        "account_id": account_id,
        "status": status,
        "message": message,
    }


def task_result_msg(task_id: str, account_id: Optional[int],
                    result: dict) -> dict:
    return {
        "type": TYPE_TASK_RESULT,
        "task_id": task_id,
        "account_id": account_id,
        "result": result,
    }


def task_event_msg(task_id: str, event_type: str, message: str = "",
                   account_id: Optional[int] = None) -> dict:
    return {
        "type": TYPE_TASK_EVENT,
        "task_id": task_id,
        "account_id": account_id,
        "event": event_type,
        "message": message,
    }


def check_orders_msg(website_id: int, source_order_nos: list,
                     request_id: str) -> dict:
    return {
        "type": TYPE_CHECK_ORDERS,
        "website_id": website_id,
        "source_order_nos": list(source_order_nos),
        "request_id": request_id,
    }


def order_detected_msg(account_id: int, order_wire: dict) -> dict:
    return {
        "type": TYPE_ORDER_DETECTED,
        "account_id": account_id,
        "order": order_wire,
    }


def trade_offer_decision_msg(assignment_id: str, accepted: bool,
                             reason: str = "") -> dict:
    return {
        "type": TYPE_TRADE_OFFER_DECISION,
        "assignment_id": assignment_id,
        "accepted": accepted,
        "reason": reason,
    }


def trade_status_msg(assignment_id: str, status: str,
                     message: str = "", error_code: str = "") -> dict:
    return {
        "type": TYPE_TRADE_STATUS,
        "assignment_id": assignment_id,
        "status": status,
        "message": message,
        "error_code": error_code,
    }


def trade_buyer_review_msg(assignment_id: str, review: dict) -> dict:
    return {
        "type": TYPE_TRADE_BUYER_REVIEW,
        "assignment_id": assignment_id,
        **review,
    }


def trade_game_screenshot_msg(
        assignment_id: str, request_id: str, screenshot_path: str) -> dict:
    return {
        "type": TYPE_TRADE_GAME_SCREENSHOT,
        "assignment_id": assignment_id,
        "request_id": request_id,
        "screenshot_path": screenshot_path,
    }


def greeting_result_msg(order_id: int, success: bool,
                        message: str = "") -> dict:
    return {
        "type": TYPE_GREETING_RESULT,
        "order_id": order_id,
        "success": success,
        "message": message,
    }


def chat_result_msg(request_id: str, order_id: int, success: bool,
                    message: str = "", purpose: str = "manual",
                    details: Optional[dict] = None) -> dict:
    result = {
        "type": TYPE_CHAT_RESULT,
        "request_id": request_id,
        "order_id": order_id,
        "success": success,
        "message": message,
        "purpose": purpose,
    }
    if details:
        result["details"] = details
    return result
