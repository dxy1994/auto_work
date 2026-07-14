"""
自动化回报门面。

浏览器自动化代码通过 get_reporter() 获取当前 Reporter，把任务状态、
验证码请求等经 agent 上报总控，避免逐层传参与直接依赖数据库/WS。

一个 worker 进程只有一条总控连接，故使用模块级单例。
"""
import threading
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
        self._captcha_values: dict = {}
        self._captcha_events: dict = {}

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

    # ── 验证码交互（跨线程）──
    def report_captcha_required(self, task_id):
        with self._lock:
            self._captcha_events.setdefault(task_id, threading.Event())
        self._client.send_threadsafe({
            "type": "captcha_required",
            "task_id": task_id,
        })

    def deliver_captcha(self, task_id, value):
        """由 WS 接收循环调用：交付前端回填的验证码。"""
        with self._lock:
            self._captcha_values[task_id] = value
            ev = self._captcha_events.setdefault(task_id, threading.Event())
        ev.set()

    def wait_captcha(self, task_id, timeout: int = 60) -> str:
        """工作线程阻塞等待验证码，超时返回空串。"""
        with self._lock:
            ev = self._captcha_events.setdefault(task_id, threading.Event())
        got = ev.wait(timeout)
        with self._lock:
            val = self._captcha_values.pop(task_id, "") if got else ""
            self._captcha_events.pop(task_id, None)
        return val
