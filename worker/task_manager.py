"""
任务管理：在工作线程中运行同步的浏览器自动化任务，支持按 account_id 终止。
"""
import threading
import time


class TaskManager:
    def __init__(self, reporter):
        self._reporter = reporter
        self._lock = threading.Lock()
        # account_id -> {"thread", "stop_event", "task_id", "status", "start_time"}
        self._tasks: dict = {}

    def start_order_check(self, task_id, account_id, runner) -> bool:
        """启动订单监控。runner: callable(stop_event) -> None。

        返回 False 表示该账号已有任务在运行。
        """
        return self._start_task(task_id, account_id, "order_check", runner)

    def cancel(self, account_id) -> bool:
        with self._lock:
            info = self._tasks.get(account_id)
            if not info or info["status"] != "running":
                return False
            info["stop_event"].set()
            info["status"] = "stopping"
            return True

    def cancel_all(self, join_timeout=5.0) -> int:
        """停止当前连接创建的所有任务，并有限等待线程清理。"""
        with self._lock:
            tasks = list(self._tasks.items())
            for _, info in tasks:
                info["stop_event"].set()
                info["status"] = "stopping"

        deadline = time.monotonic() + max(0, join_timeout)
        for _, info in tasks:
            thread = info["thread"]
            if thread is threading.current_thread():
                continue
            thread.join(max(0, deadline - time.monotonic()))

        with self._lock:
            for account_id, info in tasks:
                if not info["thread"].is_alive():
                    current = self._tasks.get(account_id)
                    if current and current["task_id"] == info["task_id"]:
                        self._tasks.pop(account_id, None)
        return len(tasks)

    def snapshot(self) -> dict:
        """返回不包含线程对象的任务快照，供状态检查和测试使用。"""
        with self._lock:
            return {
                account_id: {
                    "task_id": info["task_id"],
                    "kind": info["kind"],
                    "status": info["status"],
                    "start_time": info["start_time"],
                }
                for account_id, info in self._tasks.items()
            }

    def _start_task(self, task_id, account_id, kind, runner) -> bool:
        if account_id is None:
            return False
        with self._lock:
            info = self._tasks.get(account_id)
            if info and info["status"] in ("running", "stopping"):
                return False
            stop_event = threading.Event()

            def _wrap():
                try:
                    runner(stop_event)
                finally:
                    with self._lock:
                        current = self._tasks.get(account_id)
                        if current and current["task_id"] == task_id:
                            self._tasks.pop(account_id, None)

            thread = threading.Thread(target=_wrap, daemon=True)
            self._tasks[account_id] = {
                "thread": thread,
                "stop_event": stop_event,
                "task_id": task_id,
                "kind": kind,
                "status": "running",
                "start_time": time.time(),
            }
            thread.start()
            return True
