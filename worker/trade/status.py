"""线程安全的游戏客户端运行态快照。"""

import threading


class RuntimeStatus:
    _FIELDS = {
        "game_id",
        "game_account_id",
        "region_id",
        "client_status",
        "character_name",
        "executor_status",
        "current_assignment_id",
        "ui_health",
    }

    def __init__(self):
        self._lock = threading.Lock()
        self._values = {
            "game_id": None,
            "game_account_id": None,
            "region_id": None,
            "client_status": "unknown",
            "character_name": None,
            "executor_status": "idle",
            "current_assignment_id": None,
            "ui_health": "unknown",
        }

    def update(self, **values):
        unknown = set(values) - self._FIELDS
        if unknown:
            raise ValueError(f"unknown runtime fields: {sorted(unknown)}")
        with self._lock:
            self._values.update(values)

    def snapshot(self):
        with self._lock:
            return dict(self._values)
