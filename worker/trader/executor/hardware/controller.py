"""
ESP32C3 + CH9329 键鼠硬件控制器。

通过 HTTP/socket 向 ESP32C3 发送键鼠指令，
ESP32C3 固件通过 CH9329 芯片将指令转为 USB HID 信号。

通信协议（待定）：
    POST http://<esp32_ip>/mouse/move   {"x": 320, "y": 240, "trajectory": "bezier"}
    POST http://<esp32_ip>/mouse/click  {"button": "left"}
    POST http://<esp32_ip>/key/press    {"key": "F3", "duration_ms": 100}
    GET  http://<esp32_ip>/health
"""
import random
import time
from typing import Optional


class HardwareController:
    """键鼠硬件控制器（占位实现，待 ESP32C3 固件就绪后对接）。"""

    def __init__(self, esp32_host: str = "192.168.1.100"):
        self._host = esp32_host
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    def connect(self) -> bool:
        """连接 ESP32C3 硬件。"""
        print(f"[HW] 尝试连接 ESP32C3 @ {self._host} ...")
        # TODO: 实际 HTTP/socket 连接
        self._connected = True
        print(f"[HW] ESP32C3 连接成功")
        return True

    def disconnect(self):
        """断开连接。"""
        self._connected = False
        print(f"[HW] ESP32C3 已断开")

    # ── 鼠标操作 ──

    def mouse_move(self, x: int, y: int, trajectory: str = "human") -> bool:
        """移动鼠标到目标坐标。

        Args:
            x, y: 目标坐标（屏幕像素）
            trajectory: 轨迹类型
                - "human": 贝塞尔曲线 + 随机抖动 + 加减速
                - "linear": 直线（仅调试用，高反作弊风险）
        """
        if not self._connected:
            return False
        # 随机偏移（模拟人类不精确点击，±5px）
        x = x + random.randint(-5, 5)
        y = y + random.randint(-5, 5)
        print(f"[HW] mouse_move → ({x}, {y}) trajectory={trajectory}")
        # TODO: HTTP POST to ESP32C3
        time.sleep(0.05)  # 模拟移动耗时
        return True

    def mouse_click(self, button: str = "left") -> bool:
        """点击鼠标。"""
        if not self._connected:
            return False
        print(f"[HW] mouse_click button={button}")
        # TODO: HTTP POST to ESP32C3
        return True

    def mouse_double_click(self, button: str = "left") -> bool:
        """双击鼠标。"""
        if not self._connected:
            return False
        print(f"[HW] mouse_double_click button={button}")
        self.mouse_click(button)
        time.sleep(0.08 + random.random() * 0.05)
        self.mouse_click(button)
        return True

    def mouse_drag(self, x1: int, y1: int, x2: int, y2: int) -> bool:
        """拖拽鼠标。"""
        if not self._connected:
            return False
        print(f"[HW] mouse_drag ({x1},{y1}) → ({x2},{y2})")
        # TODO: HTTP POST to ESP32C3
        return True

    # ── 键盘操作 ──

    def key_press(self, key: str, duration_ms: int = 100) -> bool:
        """按下并释放按键。"""
        if not self._connected:
            return False
        print(f"[HW] key_press key={key} duration={duration_ms}ms")
        # TODO: HTTP POST to ESP32C3
        return True

    def key_combo(self, keys: list, duration_ms: int = 100) -> bool:
        """组合键（如 Ctrl+C）。"""
        if not self._connected:
            return False
        print(f"[HW] key_combo keys={keys}")
        # TODO: 同时按下所有键，延迟后释放
        return True

    def key_type(self, text: str, delay_ms: int = 50) -> bool:
        """逐字输入文本。"""
        if not self._connected:
            return False
        print(f"[HW] key_type text='{text}' delay={delay_ms}ms")
        for ch in text:
            self.key_press(ch, duration_ms=delay_ms)
            time.sleep(random.uniform(0.03, 0.08))
        return True

    # ── 等待操作 ──

    def wait(self, ms: int, jitter: int = 0) -> bool:
        """等待指定毫秒（可选随机抖动）。"""
        if jitter > 0:
            ms = ms + random.randint(-jitter, jitter)
        ms = max(0, ms)
        time.sleep(ms / 1000.0)
        return True

    # ── 健康检查 ──

    def health_check(self) -> Optional[dict]:
        """查询硬件状态。"""
        if not self._connected:
            return None
        # TODO: GET http://<esp32_ip>/health
        return {
            "connected": True,
            "host": self._host,
        }
