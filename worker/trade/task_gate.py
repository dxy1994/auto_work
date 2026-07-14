"""总控两阶段指派在 Worker 侧的单槽门禁。"""

import hmac
import threading


class TradeTaskGate:
    def __init__(self):
        self._lock = threading.Lock()
        self._status = "idle"
        self._assignment_id = None
        self._token = None

    def offer(self, assignment_id, token):
        if not assignment_id or not token:
            return False, "invalid_offer"
        with self._lock:
            if self._status == "idle":
                self._status = "offered"
                self._assignment_id = assignment_id
                self._token = token
                return True, "accepted"
            if (self._status == "offered"
                    and self._assignment_id == assignment_id
                    and hmac.compare_digest(self._token, token)):
                return True, "accepted"
            return False, "executor_busy"

    def start(self, assignment_id, token):
        with self._lock:
            if self._status == "running":
                return (self._assignment_id == assignment_id
                        and hmac.compare_digest(self._token, token))
            if (self._status != "offered"
                    or self._assignment_id != assignment_id
                    or not hmac.compare_digest(self._token or "", token or "")):
                return False
            self._status = "running"
            return True

    def complete(self, assignment_id):
        with self._lock:
            if self._status != "running" or self._assignment_id != assignment_id:
                return False
            self._clear()
            return True

    def cancel(self, assignment_id):
        with self._lock:
            if self._status == "idle" or self._assignment_id != assignment_id:
                return False
            self._clear()
            return True

    def snapshot(self):
        with self._lock:
            return {
                "status": self._status,
                "assignment_id": self._assignment_id,
            }

    def _clear(self):
        self._status = "idle"
        self._assignment_id = None
        self._token = None


trade_task_gate = TradeTaskGate()
