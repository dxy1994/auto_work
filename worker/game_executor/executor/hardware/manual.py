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
        self._coordinate_context: dict[str, object] = {}
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

    def set_coordinate_context(self, context):
        self._coordinate_context = dict(context or {})

    def mouse_click(self, button="left"):
        x, y = self._cursor or (None, None)
        context = self._take_coordinate_context()
        client_actual = context.get("client_actual")
        client_origin = context.get("client_origin")
        client_action_bounds = context.get("client_action_bounds")
        if isinstance(client_actual, list) and isinstance(client_origin, list):
            action_range_text = ""
            if isinstance(client_action_bounds, list):
                action_range_text = (
                    f"；允许操作范围 X[{client_action_bounds[0]},"
                    f"{client_action_bounds[2]}] "
                    f"Y[{client_action_bounds[1]},"
                    f"{client_action_bounds[3]}]"
                )
            instruction = (
                f"请手动在游戏客户区坐标 "
                f"({client_actual[0]},{client_actual[1]}) "
                f"执行{self._button_name(button)}单击"
                f"（屏幕绝对坐标 ({x},{y})；"
                f"客户区原点 ({client_origin[0]},{client_origin[1]})"
                f"{action_range_text}）"
            )
        else:
            instruction = (
                f"请手动在屏幕坐标 ({x},{y}) "
                f"执行{self._button_name(button)}单击"
            )
        return self._required_action(
            "mouse_click",
            instruction,
            x=x,
            y=y,
            button=button,
            **context,
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
        context = self._take_coordinate_context()
        client_start = context.get("client_actual_start")
        client_end = context.get("client_actual_end")
        client_origin = context.get("client_origin")
        if (
            isinstance(client_start, list)
            and isinstance(client_end, list)
            and isinstance(client_origin, list)
        ):
            instruction = (
                f"请手动从游戏客户区坐标 ({client_start[0]},{client_start[1]}) "
                f"拖拽到 ({client_end[0]},{client_end[1]})"
                f"（屏幕绝对坐标 ({int(x1)},{int(y1)}) "
                f"到 ({int(x2)},{int(y2)})；"
                f"客户区原点 ({client_origin[0]},{client_origin[1]})）"
            )
        else:
            instruction = (
                f"请手动从屏幕坐标 ({int(x1)},{int(y1)}) "
                f"拖拽到 ({int(x2)},{int(y2)})"
            )
        return self._required_action(
            "mouse_drag",
            instruction,
            x1=int(x1),
            y1=int(y1),
            x2=int(x2),
            y2=int(y2),
            **context,
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

    def key_type_plan(self, text, plan):
        """合并输出拟人化逐字计划，避免人工模式要求操作者逐字确认。"""
        return self._required_action(
            "key_type",
            f"请手动输入：{text}",
            text=str(text),
            typing_plan=plan,
            humanized=True,
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

    def _take_coordinate_context(self):
        context = self._coordinate_context
        self._coordinate_context = {}
        return context

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
