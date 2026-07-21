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
import json
import time
from typing import Optional
from urllib.error import URLError
from urllib.request import Request, urlopen


class HardwareController:
    """通过 ESP32C3 HTTP 网关发送真实 USB HID 指令。"""

    def __init__(self, esp32_host: str = "192.168.1.100"):
        host = esp32_host.strip().rstrip("/")
        self._base_url = host if host.startswith(("http://", "https://")) else f"http://{host}"
        self._host = host
        self._connected = False

    def _request(self, method: str, path: str, payload: Optional[dict] = None):
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            f"{self._base_url}{path}",
            data=body,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=2.0) as response:
                raw = response.read()
                if not 200 <= response.status < 300:
                    return None
                if not raw:
                    return {"ok": True}
                try:
                    return json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    return {"ok": True}
        except (OSError, URLError) as exc:
            print(f"[HW] {method} {path} 失败: {exc}")
            self._connected = False
            return None

    @staticmethod
    def _response_ok(response) -> bool:
        if response is None:
            return False
        if isinstance(response, dict):
            return response.get("ok", True) is not False and response.get("success", True) is not False
        return True

    @property
    def connected(self) -> bool:
        return self._connected

    def connect(self) -> bool:
        """连接 ESP32C3 硬件。"""
        print(f"[HW] 尝试连接 ESP32C3 @ {self._host} ...")
        health = self._request("GET", "/health")
        self._connected = self._response_ok(health) and not (
            isinstance(health, dict) and health.get("connected") is False
        )
        if not self._connected:
            print("[HW] ESP32C3 连接失败")
            return False
        print(f"[HW] ESP32C3 连接成功")
        return True

    def disconnect(self):
        """断开连接。"""
        self._connected = False
        print(f"[HW] ESP32C3 已断开")

    # ── 鼠标操作 ──

    def mouse_move(
        self,
        x: int,
        y: int,
        trajectory: str = "human",
        jitter_x: int = 5,
        jitter_y: int = 5,
    ) -> bool:
        """移动鼠标到目标坐标。

        Args:
            x, y: 目标坐标（屏幕像素）
            trajectory: 轨迹类型
                - "human": 贝塞尔曲线 + 随机抖动 + 加减速
                - "linear": 直线（仅调试用，高反作弊风险）
        """
        if not self._connected:
            return False
        # 默认模拟人类不精确移动；调用方也可关闭抖动，避免叠加已计算的点位偏移。
        x = x + random.randint(-jitter_x, jitter_x) if jitter_x else x
        y = y + random.randint(-jitter_y, jitter_y) if jitter_y else y
        print(f"[HW] mouse_move → ({x}, {y}) trajectory={trajectory}")
        return self._response_ok(self._request("POST", "/mouse/move", {
            "x": x, "y": y, "trajectory": trajectory,
        }))

    def mouse_click(self, button: str = "left") -> bool:
        """点击鼠标。"""
        if not self._connected:
            return False
        print(f"[HW] mouse_click button={button}")
        return self._response_ok(
            self._request("POST", "/mouse/click", {"button": button}))

    def mouse_double_click(self, button: str = "left") -> bool:
        """双击鼠标。"""
        if not self._connected:
            return False
        print(f"[HW] mouse_double_click button={button}")
        if not self.mouse_click(button):
            return False
        time.sleep(0.08 + random.random() * 0.05)
        return self.mouse_click(button)

    def mouse_drag(self, x1: int, y1: int, x2: int, y2: int) -> bool:
        """拖拽鼠标。"""
        if not self._connected:
            return False
        print(f"[HW] mouse_drag ({x1},{y1}) → ({x2},{y2})")
        return self._response_ok(self._request("POST", "/mouse/drag", {
            "x1": x1, "y1": y1, "x2": x2, "y2": y2, "trajectory": "human",
        }))

    # ── 键盘操作 ──

    def key_press(self, key: str, duration_ms: int = 100) -> bool:
        """按下并释放按键。"""
        if not self._connected:
            return False
        print(f"[HW] key_press key={key} duration={duration_ms}ms")
        return self._response_ok(self._request("POST", "/key/press", {
            "key": key, "duration_ms": duration_ms,
        }))

    def key_combo(self, keys: list, duration_ms: int = 100) -> bool:
        """组合键（如 Ctrl+C）。"""
        if not self._connected:
            return False
        print(f"[HW] key_combo keys={keys}")
        return self._response_ok(self._request("POST", "/key/combo", {
            "keys": keys, "duration_ms": duration_ms,
        }))

    def key_type(self, text: str, delay_ms: int = 50) -> bool:
        """逐字输入文本。"""
        if not self._connected:
            return False
        print(f"[HW] key_type text='{text}' delay={delay_ms}ms")
        for ch in text:
            if not self.key_press(ch, duration_ms=delay_ms):
                return False
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
        health = self._request("GET", "/health")
        if not self._response_ok(health):
            return None
        details = health if isinstance(health, dict) else {"response": health}
        return {"connected": True, "host": self._host, **details}
