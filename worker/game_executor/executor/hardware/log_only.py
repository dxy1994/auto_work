"""正式指令演练用硬件控制器：记录 HID 动作，但绝不发送。"""

import json
import time


class LogOnlyHardwareController:
    """实现正式硬件接口，所有键鼠动作只输出日志。"""

    log_only = True

    def __init__(self):
        self._connected = True
        self.planned_actions = 0

    @property
    def connected(self):
        return self._connected

    def connect(self):
        self._log("connect", mode="log_only", sent=False)
        return True

    def disconnect(self):
        self._connected = False
        self._log("disconnect", sent=False)

    def mouse_move(self, x, y, trajectory="human", jitter_x=5, jitter_y=5):
        return self._action(
            "mouse_move",
            x=int(x),
            y=int(y),
            trajectory=trajectory,
            jitter_x=jitter_x,
            jitter_y=jitter_y,
        )

    def mouse_click(self, button="left"):
        return self._action("mouse_click", button=button)

    def mouse_double_click(self, button="left"):
        return self._action("mouse_double_click", button=button)

    def mouse_drag(self, x1, y1, x2, y2):
        return self._action(
            "mouse_drag", x1=int(x1), y1=int(y1), x2=int(x2), y2=int(y2)
        )

    def key_press(self, key, duration_ms=100):
        return self._action("key_press", key=str(key), duration_ms=duration_ms)

    def key_combo(self, keys, duration_ms=100):
        return self._action("key_combo", keys=list(keys), duration_ms=duration_ms)

    def key_type(self, text, delay_ms=50):
        return self._action("key_type", text=str(text), delay_ms=delay_ms)

    def wait(self, ms, jitter=0):
        delay_ms = max(0, int(ms))
        self._log("wait", duration_ms=delay_ms, jitter=jitter, sent=False)
        time.sleep(delay_ms / 1000.0)
        return True

    def health_check(self):
        return {
            "connected": True,
            "mode": "log_only",
            "planned_actions": self.planned_actions,
            "hid_commands_sent": 0,
        }

    def _action(self, action, **values):
        self.planned_actions += 1
        self._log(action, **values, sent=False)
        return True

    @staticmethod
    def _log(action, **values):
        print(
            "[HID-DRY-RUN] "
            + json.dumps(
                {"action": action, **values},
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
