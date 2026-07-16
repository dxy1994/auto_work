"""
自动化回报门面。

浏览器自动化代码通过 get_reporter() 获取当前 Reporter，把任务状态、
订单数据等经 agent 上报总控，避免逐层传参与直接依赖数据库/WS。

一个 worker 进程只有一条总控连接，故使用模块级单例。
"""
import threading
import uuid
from typing import Optional

_current: Optional["Reporter"] = None


def set_reporter(reporter: "Reporter"):
    global _current
    _current = reporter


def get_reporter() -> "Reporter":
    if _current is None:
        raise RuntimeError("Reporter 未初始化")
    return _current


class Reporter:
    def __init__(self, client):
        self._client = client
        self._lock = threading.Lock()
        self._order_check_events: dict = {}
        self._order_check_results: dict = {}

    # ── 状态上报 ──
    def report_status(self, task_id, status, message="", account_id=None):
        self._client.send_threadsafe({
            "type": "task_status",
            "task_id": task_id,
            "account_id": account_id,
            "status": status,
            "message": message,
        })

    def report_result(self, task_id, account_id, result):
        self._client.send_threadsafe({
            "type": "task_result",
            "task_id": task_id,
            "account_id": account_id,
            "result": result,
        })

    def report_event(self, task_id, event_type, message="", account_id=None):
        """转发给前端的通用事件（manual_login_ready/login_success/login_timeout 等）。"""
        self._client.send_threadsafe({
            "type": "task_event",
            "task_id": task_id,
            "account_id": account_id,
            "event": event_type,
            "message": message,
        })

    def report_trade_offer_decision(self, assignment_id, accepted, reason=""):
        self._client.send_threadsafe({
            "type": "trade_offer_decision",
            "assignment_id": assignment_id,
            "accepted": accepted,
            "reason": reason,
        })

    def report_trade_status(self, assignment_id, status, message=""):
        self._client.send_threadsafe({
            "type": "trade_status",
            "assignment_id": assignment_id,
            "status": status,
            "message": message,
        })

    def report_order_detected(self, account_id, order):
        self._client.send_threadsafe({
            "type": "order_detected",
            "account_id": account_id,
            "order": order.to_wire(),
        })

    def report_greeting_result(self, order_id, success, message=""):
        self._client.send_threadsafe({
            "type": "greeting_result",
            "order_id": order_id,
            "success": success,
            "message": message,
        })

    # ── 订单查重（跨线程请求-响应）──

    def check_existing_orders(self, website_id, source_order_nos, timeout=5):
        """批量查重：向总控查询哪些 source_order_no 已入库，返回集合。
        超时或失败返回空集（fail-open，保证不会漏单）。"""
        if not source_order_nos:
            return set()
        request_id = str(uuid.uuid4())[:8]
        ev = threading.Event()
        with self._lock:
            self._order_check_events[request_id] = ev
        try:
            self._client.send_threadsafe({
                "type": "check_orders",
                "website_id": website_id,
                "source_order_nos": list(source_order_nos),
                "request_id": request_id,
            })
        except Exception as e:
            print(f"[Reporter] 查重请求发送失败: {e}")
            with self._lock:
                self._order_check_events.pop(request_id, None)
            return set()
        got = ev.wait(timeout)
        with self._lock:
            result = self._order_check_results.pop(request_id, set()) if got else set()
            self._order_check_events.pop(request_id, None)
        return result

    def deliver_orders_check_result(self, request_id, existing_ids):
        """由 WS 接收循环调用：交付总控返回的查重结果。"""
        with self._lock:
            self._order_check_results[request_id] = set(existing_ids or [])
            ev = self._order_check_events.get(request_id)
        if ev:
            ev.set()

