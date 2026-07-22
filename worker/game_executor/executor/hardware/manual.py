"""人工操作测试控制器：输出真实动作指引，但绝不发送 HID。"""

from __future__ import annotations

import json
import time


class ManualActionHardwareController:
    """实现正式硬件接口，由操作者根据日志手动完成键鼠动作。"""

    manual_mode = True
    log_only = True

    def __init__(self, action_wait_seconds: float = 5.0):
        self._connected = True
        self._cursor: tuple[int, int] | None = None
        self._action_wait_seconds = max(0.0, float(action_wait_seconds))
        self.planned_actions = 0

    @property
    def connected(self):
        return self._connected

    def connect(self):
        self._log(
            "ready",
            instruction="人工操作测试控制器已就绪，不会连接 ESP32 或发送 HID",
            hid_sent=False,
        )
        return True

    def disconnect(self):
        self._connected = False
        self._log("disconnect", instruction="人工操作测试控制器已停止", hid_sent=False)

    def mouse_move(self, x, y, trajectory="human", jitter_x=5, jitter_y=5):
        # 正式执行器通常会紧接着调用 click；在点击日志中合并输出绝对坐标，避免重复等待。
        self._cursor = (int(x), int(y))
        return True

    def mouse_click(self, button="left"):
        x, y = self._cursor or (None, None)
        return self._required_action(
            "mouse_click",
            f"请手动在屏幕坐标 ({x},{y}) 执行{self._button_name(button)}单击",
            x=x,
            y=y,
            button=button,
        )

    def mouse_double_click(self, button="left"):
        x, y = self._cursor or (None, None)
        return self._required_action(
            "mouse_double_click",
            f"请手动在屏幕坐标 ({x},{y}) 执行{self._button_name(button)}双击",
            x=x,
            y=y,
            button=button,
        )

    def mouse_drag(self, x1, y1, x2, y2):
        return self._required_action(
            "mouse_drag",
            f"请手动从屏幕坐标 ({int(x1)},{int(y1)}) 拖拽到 ({int(x2)},{int(y2)})",
            x1=int(x1),
            y1=int(y1),
            x2=int(x2),
            y2=int(y2),
        )

    def key_press(self, key, duration_ms=100):
        return self._required_action(
            "key_press",
            f"请手动按键 {key}",
            key=str(key),
            duration_ms=duration_ms,
        )

    def key_combo(self, keys, duration_ms=100):
        normalized = [str(key) for key in keys]
        return self._required_action(
            "key_combo",
            "请手动按组合键 " + "+".join(normalized),
            keys=normalized,
            duration_ms=duration_ms,
        )

    def key_type(self, text, delay_ms=50):
        return self._required_action(
            "key_type",
            f"请手动输入：{text}",
            text=str(text),
            delay_ms=delay_ms,
        )

    def wait(self, ms, jitter=0):
        delay_ms = max(0, int(ms))
        self._log(
            "wait",
            instruction=f"等待 {delay_ms}ms",
            duration_ms=delay_ms,
            jitter=jitter,
            hid_sent=False,
        )
        time.sleep(delay_ms / 1000.0)
        return True

    def health_check(self):
        return {
            "connected": True,
            "mode": "manual_actions",
            "planned_actions": self.planned_actions,
            "hid_commands_sent": 0,
            "action_wait_seconds": self._action_wait_seconds,
        }

    def _required_action(self, action, instruction, **values):
        self.planned_actions += 1
        self._log(
            action,
            sequence=self.planned_actions,
            instruction=instruction,
            manual_action_wait_seconds=self._action_wait_seconds,
            hid_sent=False,
            **values,
        )
        if self._action_wait_seconds:
            time.sleep(self._action_wait_seconds)
        return True

    @staticmethod
    def _button_name(button):
        return {"left": "鼠标左键", "right": "鼠标右键"}.get(str(button), f"鼠标{button}键")

    @staticmethod
    def _log(action, **values):
        print(
            "[MANUAL-ACTION] "
            + json.dumps(
                {"action": action, **values},
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            flush=True,
        )
