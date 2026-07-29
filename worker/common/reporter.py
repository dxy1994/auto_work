"""自动化回报门面。

浏览器自动化代码通过 Reporter 把任务状态、订单数据等经 Agent 上报总控，
避免逐层传参与直接依赖数据库/WS。
"""
import threading
import uuid
from typing import Optional

from common.protocol import (
    task_status_msg, task_result_msg, task_event_msg,
    check_orders_msg, order_detected_msg,
    trade_offer_decision_msg, trade_status_msg, trade_buyer_review_msg,
    trade_game_screenshot_msg,
    greeting_result_msg,
    chat_result_msg,
)


class Reporter:
    """上报门面：将自动化结果通过 AgentClient 发送到总控。

    实例化时注入 AgentClient，不再依赖模块级单例。
    """

    def __init__(self, client):
        self._client = client
        self._lock = threading.Lock()
        self._order_check_events: dict = {}
        self._order_check_results: dict = {}
        self._trade_screenshot_events: dict = {}
        self._trade_screenshot_results: dict = {}

    def set_client(self, client):
        """WebSocket 重连后切换发送通道，同时保留正在运行任务的 Reporter 引用。"""
        with self._lock:
            self._client = client

    # ── 状态上报 ──

    def report_status(self, task_id, status, message="", account_id=None):
        self._client.send_threadsafe(
            task_status_msg(task_id, status, message, account_id))

    def report_result(self, task_id, account_id, result):
        self._client.send_threadsafe(
            task_result_msg(task_id, account_id, result))

    def report_event(self, task_id, event_type, message="", account_id=None):
        self._client.send_threadsafe(
            task_event_msg(task_id, event_type, message, account_id))

    def report_trade_offer_decision(self, assignment_id, accepted, reason=""):
        self._client.send_threadsafe(
            trade_offer_decision_msg(assignment_id, accepted, reason))

    def report_trade_status(self, assignment_id, status, message="", error_code=""):
        self._client.send_threadsafe(
            trade_status_msg(assignment_id, status, message, error_code))

    def report_trade_buyer_review(self, assignment_id, review):
        self._client.send_threadsafe(
            trade_buyer_review_msg(assignment_id, review))

    def save_trade_game_screenshot(self, assignment_id, screenshot_path, timeout=10):
        request_id = str(uuid.uuid4())
        event = threading.Event()
        with self._lock:
            self._trade_screenshot_events[request_id] = event
        try:
            self._client.send_threadsafe(trade_game_screenshot_msg(
                assignment_id, request_id, screenshot_path))
            if not event.wait(timeout):
                return False
            with self._lock:
                return bool(self._trade_screenshot_results.pop(request_id, False))
        finally:
            with self._lock:
                self._trade_screenshot_events.pop(request_id, None)
                self._trade_screenshot_results.pop(request_id, None)

    def deliver_trade_game_screenshot_saved(self, request_id, success):
        with self._lock:
            event = self._trade_screenshot_events.get(request_id)
            if event is not None:
                self._trade_screenshot_results[request_id] = bool(success)
        if event:
            event.set()

    def report_order_detected(self, account_id, order):
        self._client.send_threadsafe(
            order_detected_msg(account_id, order.to_wire()))

    def report_greeting_result(self, order_id, success, message=""):
        self._client.send_threadsafe(
            greeting_result_msg(order_id, success, message))

    def report_chat_result(
            self, request_id, order_id, success, message="", purpose="manual",
            details=None):
        self._client.send_threadsafe(
            chat_result_msg(
                request_id, order_id, success, message, purpose, details
            ))

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
            self._client.send_threadsafe(
                check_orders_msg(website_id, source_order_nos, request_id))
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
