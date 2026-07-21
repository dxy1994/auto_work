"""应用上下文：依赖注入容器。

统一管理 Reporter、RuntimeStatus、TradeTaskGate 等
跨模块共享的组件生命周期，替代模块级全局单例。
"""
import asyncio
import threading
from typing import Optional


class AppContext:
    """Worker 应用上下文，管理所有跨模块共享的组件。"""

    def __init__(self, main_loop: asyncio.AbstractEventLoop):
        self._main_loop = main_loop
        self._lock = threading.Lock()

        # 延迟初始化（避免循环依赖）
        self._reporter = None
        self._task_manager = None
        self._runtime_status = None
        self._trade_task_gate = None
        self._active_trade = None

    # ── 属性访问 ──

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        return self._main_loop

    @property
    def reporter(self):
        if self._reporter is None:
            raise RuntimeError("Reporter 未初始化")
        return self._reporter

    @reporter.setter
    def reporter(self, value):
        self._reporter = value

    @property
    def task_manager(self):
        if self._task_manager is None:
            raise RuntimeError("TaskManager 未初始化")
        return self._task_manager

    @task_manager.setter
    def task_manager(self, value):
        self._task_manager = value

    @property
    def runtime_status(self):
        if self._runtime_status is None:
            raise RuntimeError("RuntimeStatus 未初始化")
        return self._runtime_status

    @runtime_status.setter
    def runtime_status(self, value):
        self._runtime_status = value

    @property
    def trade_task_gate(self):
        if self._trade_task_gate is None:
            raise RuntimeError("TradeTaskGate 未初始化")
        return self._trade_task_gate

    @trade_task_gate.setter
    def trade_task_gate(self, value):
        self._trade_task_gate = value

    def set_active_trade(self, assignment_id, executor, task):
        with self._lock:
            if self._active_trade is not None:
                raise RuntimeError("another trade execution is already active")
            self._active_trade = {
                "assignment_id": assignment_id,
                "executor": executor,
                "task": task,
            }

    def active_trade(self, assignment_id=None):
        with self._lock:
            active = self._active_trade
            if active is None:
                return None
            if assignment_id is not None and active["assignment_id"] != assignment_id:
                return None
            return dict(active)

    def clear_active_trade(self, assignment_id):
        with self._lock:
            if self._active_trade is None or self._active_trade["assignment_id"] != assignment_id:
                return False
            self._active_trade = None
            return True
