"""Real Wireless HID adapter for game-executor input commands."""

from __future__ import annotations

import math
import random
import threading
import time
from dataclasses import asdict, dataclass
from typing import Callable, Optional, Protocol

from .whid_sdk import (
    CONTROL_PORT,
    ControlClient,
    DiscoveredDevice,
    WirelessHidError,
    ascii_keystroke,
    discover_unicast,
)


ScreenBounds = tuple[int, int, int, int]


class WirelessHidClient(Protocol):
    connected: bool

    def connect(self): ...

    def status(self) -> dict: ...

    def keyboard(self, modifier: int = 0, keys=(), *, tap: bool = True) -> None: ...

    def mouse_relative(
        self,
        buttons: int = 0,
        x: int = 0,
        y: int = 0,
        wheel: int = 0,
    ) -> None: ...

    def mouse_absolute(
        self,
        buttons: int = 0,
        x: int = 0,
        y: int = 0,
        wheel: int = 0,
    ) -> None: ...

    def release_all(self) -> None: ...

    def close(self) -> None: ...


@dataclass(frozen=True)
class CommandFeedback:
    """Result retained after one complete hardware instruction."""

    sequence: int
    action: str
    success: bool
    duration_ms: int
    completed_at: float
    error: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


_BUTTONS = {
    "left": 0x01,
    "right": 0x02,
    "middle": 0x04,
}

_MODIFIERS = {
    "ctrl": 0x01,
    "control": 0x01,
    "shift": 0x02,
    "alt": 0x04,
    "gui": 0x08,
    "win": 0x08,
    "windows": 0x08,
}

_SPECIAL_KEYS = {
    "ENTER": 0x28,
    "RETURN": 0x28,
    "ESC": 0x29,
    "ESCAPE": 0x29,
    "BACKSPACE": 0x2A,
    "TAB": 0x2B,
    "SPACE": 0x2C,
    "CAPSLOCK": 0x39,
    "F1": 0x3A,
    "F2": 0x3B,
    "F3": 0x3C,
    "F4": 0x3D,
    "F5": 0x3E,
    "F6": 0x3F,
    "F7": 0x40,
    "F8": 0x41,
    "F9": 0x42,
    "F10": 0x43,
    "F11": 0x44,
    "F12": 0x45,
    "PRINTSCREEN": 0x46,
    "SCROLLLOCK": 0x47,
    "PAUSE": 0x48,
    "INSERT": 0x49,
    "HOME": 0x4A,
    "PAGEUP": 0x4B,
    "DELETE": 0x4C,
    "END": 0x4D,
    "PAGEDOWN": 0x4E,
    "RIGHT": 0x4F,
    "LEFT": 0x50,
    "DOWN": 0x51,
    "UP": 0x52,
}


class HardwareController:
    """Translate game actions into WHID/1 TCP commands.

    The public API intentionally matches the old HTTP placeholder so game
    executors do not need device-specific protocol code.
    """

    def __init__(
        self,
        host: str = "192.168.1.31",
        port: int = CONTROL_PORT,
        *,
        client_factory: Callable[[str, int], WirelessHidClient] = ControlClient,
        random_source: Optional[random.Random] = None,
        sleep: Callable[[float], None] = time.sleep,
        screen_bounds: Optional[ScreenBounds] = None,
        cursor_provider: Optional[Callable[[], tuple[int, int]]] = None,
        feedback_callback: Optional[Callable[[CommandFeedback], None]] = None,
        expected_device_id: Optional[str] = None,
        discovery: Callable[[str, float], Optional[DiscoveredDevice]] = discover_unicast,
    ):
        self._host = str(host).strip()
        self._port = int(port)
        self._client_factory = client_factory
        self._random = random_source or random.Random()
        self._sleep = sleep
        self._configured_screen_bounds = screen_bounds
        self._cursor_provider = cursor_provider
        self._feedback_callback = feedback_callback
        self._expected_device_id = (
            str(expected_device_id).strip().upper() if expected_device_id else None
        )
        self._discovery = discovery
        self._client: Optional[WirelessHidClient] = None
        self._connected = False
        self._cursor: Optional[tuple[int, int]] = None
        self._feedback_sequence = 0
        self._last_feedback: Optional[CommandFeedback] = None
        self._lock = threading.RLock()

    @property
    def connected(self) -> bool:
        client_connected = bool(
            self._client is not None and getattr(self._client, "connected", True)
        )
        return self._connected and client_connected

    @property
    def last_feedback(self) -> Optional[dict[str, object]]:
        feedback = self._last_feedback
        return feedback.to_dict() if feedback is not None else None

    def set_feedback_callback(
        self,
        callback: Optional[Callable[[CommandFeedback], None]],
    ) -> None:
        self._feedback_callback = callback

    def connect(self) -> bool:
        started = time.monotonic()
        with self._lock:
            client: Optional[WirelessHidClient] = None
            try:
                if self._expected_device_id is not None:
                    discovered = self._discovery(self._host, 1.0)
                    if discovered is None:
                        raise WirelessHidError(
                            f"Wireless HID discovery timed out at {self._host}"
                        )
                    if discovered.device_id != self._expected_device_id:
                        raise WirelessHidError(
                            "Wireless HID identity mismatch: "
                            f"expected {self._expected_device_id}, "
                            f"received {discovered.device_id}"
                        )
                    if discovered.control_port != self._port:
                        raise WirelessHidError(
                            "Wireless HID control port mismatch: "
                            f"expected {self._port}, "
                            f"received {discovered.control_port}"
                        )
                    if not discovered.ch9329:
                        raise WirelessHidError("CH9329 is offline")
                client = self._client_factory(self._host, self._port)
                client.connect()
                status = client.status()
                if not bool(status.get("ch9329_online")):
                    raise WirelessHidError("CH9329 is offline")
                self._client = client
                self._connected = True
                self._finish("connect", True, started)
                return True
            except Exception as exc:
                if client is not None:
                    try:
                        client.close()
                    except Exception:
                        pass
                self._client = None
                self._connected = False
                self._finish("connect", False, started, exc)
                return False

    def disconnect(self) -> None:
        started = time.monotonic()
        with self._lock:
            client = self._client
            self._client = None
            self._connected = False
            try:
                if client is not None:
                    client.close()
                self._finish("disconnect", True, started)
            except Exception as exc:
                self._finish("disconnect", False, started, exc)

    def mouse_move(
        self,
        x: int,
        y: int,
        trajectory: str = "human",
        jitter_x: int = 5,
        jitter_y: int = 5,
    ) -> bool:
        started = time.monotonic()
        with self._lock:
            try:
                self._require_client()
                target = (
                    int(x) + self._random.randint(-jitter_x, jitter_x)
                    if jitter_x
                    else int(x),
                    int(y) + self._random.randint(-jitter_y, jitter_y)
                    if jitter_y
                    else int(y),
                )
                target = self._clamp_point(target)
                self._pause(0.04, 0.12)
                self._move_path(self._current_cursor(), target)
                self._pause(0.07, 0.18)
                self._finish("mouse_move", True, started)
                return True
            except Exception as exc:
                return self._fail("mouse_move", started, exc)

    def mouse_click(self, button: str = "left") -> bool:
        started = time.monotonic()
        with self._lock:
            try:
                client = self._require_client()
                mask = self._button_mask(button)
                self._pause(0.04, 0.12)
                client.mouse_relative(mask, 0, 0, 0)
                self._pause(0.055, 0.115)
                client.mouse_relative(0, 0, 0, 0)
                self._pause(0.08, 0.18)
                self._finish("mouse_click", True, started)
                return True
            except Exception as exc:
                self._release_safely()
                return self._fail("mouse_click", started, exc)

    def mouse_double_click(self, button: str = "left") -> bool:
        started = time.monotonic()
        with self._lock:
            try:
                client = self._require_client()
                mask = self._button_mask(button)
                for index in range(2):
                    client.mouse_relative(mask, 0, 0, 0)
                    self._pause(0.05, 0.10)
                    client.mouse_relative(0, 0, 0, 0)
                    if index == 0:
                        self._pause(0.09, 0.15)
                self._pause(0.08, 0.18)
                self._finish("mouse_double_click", True, started)
                return True
            except Exception as exc:
                self._release_safely()
                return self._fail("mouse_double_click", started, exc)

    def mouse_drag(self, x1: int, y1: int, x2: int, y2: int) -> bool:
        started = time.monotonic()
        with self._lock:
            try:
                client = self._require_client()
                start = self._clamp_point((int(x1), int(y1)))
                end = self._clamp_point((int(x2), int(y2)))
                self._move_path(self._current_cursor(), start)
                self._pause(0.10, 0.24)
                sx, sy = self._normalize_point(start)
                client.mouse_absolute(_BUTTONS["left"], sx, sy, 0)
                self._pause(0.07, 0.15)
                self._move_path(start, end, buttons=_BUTTONS["left"])
                self._pause(0.06, 0.14)
                ex, ey = self._normalize_point(end)
                client.mouse_absolute(0, ex, ey, 0)
                self._cursor = end
                self._pause(0.10, 0.22)
                self._finish("mouse_drag", True, started)
                return True
            except Exception as exc:
                self._release_safely()
                return self._fail("mouse_drag", started, exc)

    def mouse_scroll(self, steps: int) -> bool:
        """Scroll in discrete notches; negative values scroll down."""
        started = time.monotonic()
        with self._lock:
            try:
                client = self._require_client()
                resolved_steps = int(steps)
                if not -100 <= resolved_steps <= 100:
                    raise ValueError("scroll steps must be -100..100")
                direction = -1 if resolved_steps < 0 else 1
                self._pause(0.06, 0.14)
                for index in range(abs(resolved_steps)):
                    client.mouse_relative(0, 0, 0, direction)
                    if index + 1 < abs(resolved_steps):
                        self._pause(0.07, 0.17)
                self._pause(0.10, 0.22)
                self._finish("mouse_scroll", True, started)
                return True
            except Exception as exc:
                return self._fail("mouse_scroll", started, exc)

    def key_press(self, key: str, duration_ms: int = 100) -> bool:
        started = time.monotonic()
        with self._lock:
            try:
                client = self._require_client()
                modifier, usage = self._resolve_key(str(key))
                client.keyboard(modifier, [usage], tap=False)
                self._sleep(max(0.075, int(duration_ms) / 1000.0))
                client.keyboard(0, (), tap=False)
                self._pause(0.08, 0.20)
                self._finish("key_press", True, started)
                return True
            except Exception as exc:
                self._release_safely()
                return self._fail("key_press", started, exc)

    def key_combo(self, keys: list[str], duration_ms: int = 100) -> bool:
        started = time.monotonic()
        with self._lock:
            try:
                client = self._require_client()
                modifier = 0
                usages: list[int] = []
                for key in keys:
                    normalized = str(key).strip()
                    modifier_value = _MODIFIERS.get(normalized.lower())
                    if modifier_value is not None:
                        modifier |= modifier_value
                        continue
                    key_modifier, usage = self._resolve_key(normalized)
                    modifier |= key_modifier
                    usages.append(usage)
                if not modifier and not usages:
                    raise ValueError("key combo cannot be empty")
                client.keyboard(modifier, usages, tap=False)
                self._sleep(max(0.075, int(duration_ms) / 1000.0))
                client.keyboard(0, (), tap=False)
                self._pause(0.08, 0.20)
                self._finish("key_combo", True, started)
                return True
            except Exception as exc:
                self._release_safely()
                return self._fail("key_combo", started, exc)

    def key_type(self, text: str, delay_ms: int = 100) -> bool:
        minimum_hold = max(75, int(delay_ms))
        plan = [
            {
                "key": character,
                "hold_ms": self._random.randint(minimum_hold, max(minimum_hold, 150)),
                "gap_ms": self._random.randint(80, 220),
            }
            for character in str(text)
        ]
        return self.key_type_plan(str(text), plan)

    def key_type_plan(self, text: str, plan: list[dict[str, object]]) -> bool:
        started = time.monotonic()
        with self._lock:
            try:
                client = self._require_client()
                if len(plan) != len(text):
                    raise ValueError("typing plan length must match text length")
                for character, item in zip(text, plan):
                    if str(item.get("key", character)) != character:
                        raise ValueError("typing plan key does not match text")
                    modifier, usage = ascii_keystroke(character)
                    hold_ms = max(75, int(item.get("hold_ms", 100)))
                    gap_ms = max(80, int(item.get("gap_ms", 120)))
                    client.keyboard(modifier, [usage], tap=False)
                    self._sleep(hold_ms / 1000.0)
                    client.keyboard(0, (), tap=False)
                    self._sleep(gap_ms / 1000.0)
                self._pause(0.10, 0.22)
                self._finish("key_type", True, started)
                return True
            except Exception as exc:
                self._release_safely()
                return self._fail("key_type", started, exc)

    def wait(self, ms: int, jitter: int = 0) -> bool:
        if jitter > 0:
            ms += self._random.randint(-jitter, jitter)
        self._sleep(max(0, ms) / 1000.0)
        return True

    def health_check(self) -> Optional[dict]:
        with self._lock:
            try:
                client = self._require_client()
                status = client.status()
                online = bool(status.get("ch9329_online"))
                return {
                    "connected": True,
                    "ready": online,
                    "host": self._host,
                    "port": self._port,
                    **status,
                    "last_command": self.last_feedback,
                }
            except Exception:
                self._connected = False
                return None

    def _move_path(
        self,
        start: tuple[int, int],
        end: tuple[int, int],
        *,
        buttons: int = 0,
    ) -> None:
        client = self._require_client()
        if start == end:
            nx, ny = self._normalize_point(end)
            client.mouse_absolute(buttons, nx, ny, 0)
            self._cursor = end
            return

        dx = end[0] - start[0]
        dy = end[1] - start[1]
        distance = math.hypot(dx, dy)
        steps = max(10, min(52, round(distance / 22)))
        duration = max(0.22, min(0.95, 0.20 + distance / 1450))
        duration *= self._random.uniform(0.88, 1.16)
        perpendicular_x = -dy / distance
        perpendicular_y = dx / distance
        bend = min(90.0, max(8.0, distance * self._random.uniform(0.06, 0.15)))
        bend *= self._random.choice((-1.0, 1.0))
        c1 = (
            start[0] + dx * self._random.uniform(0.22, 0.38) + perpendicular_x * bend,
            start[1] + dy * self._random.uniform(0.22, 0.38) + perpendicular_y * bend,
        )
        c2 = (
            start[0] + dx * self._random.uniform(0.62, 0.82) + perpendicular_x * bend,
            start[1] + dy * self._random.uniform(0.62, 0.82) + perpendicular_y * bend,
        )

        last_point: Optional[tuple[int, int]] = None
        for index in range(1, steps + 1):
            t = index / steps
            inverse = 1.0 - t
            point = self._clamp_point(
                (
                    round(
                        inverse**3 * start[0]
                        + 3 * inverse**2 * t * c1[0]
                        + 3 * inverse * t**2 * c2[0]
                        + t**3 * end[0]
                    ),
                    round(
                        inverse**3 * start[1]
                        + 3 * inverse**2 * t * c1[1]
                        + 3 * inverse * t**2 * c2[1]
                        + t**3 * end[1]
                    ),
                )
            )
            if point != last_point:
                nx, ny = self._normalize_point(point)
                client.mouse_absolute(buttons, nx, ny, 0)
                last_point = point
            if index < steps:
                eased = math.sin(math.pi * t)
                interval = duration / steps * (1.15 - 0.35 * eased)
                self._sleep(max(0.008, interval))

        self._cursor = end

    def _current_cursor(self) -> tuple[int, int]:
        if self._cursor_provider is not None:
            try:
                return self._clamp_point(self._cursor_provider())
            except Exception:
                pass
        if self._cursor is not None:
            return self._clamp_point(self._cursor)
        try:
            import ctypes

            class Point(ctypes.Structure):
                _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

            point = Point()
            if ctypes.windll.user32.GetCursorPos(ctypes.byref(point)):
                return self._clamp_point((int(point.x), int(point.y)))
        except (AttributeError, OSError):
            pass
        left, top, right, bottom = self._screen_bounds()
        return ((left + right) // 2, (top + bottom) // 2)

    def _screen_bounds(self) -> ScreenBounds:
        if self._configured_screen_bounds is not None:
            return self._configured_screen_bounds
        try:
            import ctypes

            user32 = ctypes.windll.user32
            left = int(user32.GetSystemMetrics(76))
            top = int(user32.GetSystemMetrics(77))
            width = int(user32.GetSystemMetrics(78))
            height = int(user32.GetSystemMetrics(79))
            if width > 0 and height > 0:
                return left, top, left + width - 1, top + height - 1
        except (AttributeError, OSError):
            pass
        return 0, 0, 1919, 1079

    def _clamp_point(self, point: tuple[int, int]) -> tuple[int, int]:
        left, top, right, bottom = self._screen_bounds()
        return (
            min(right, max(left, int(point[0]))),
            min(bottom, max(top, int(point[1]))),
        )

    def _normalize_point(self, point: tuple[int, int]) -> tuple[int, int]:
        left, top, right, bottom = self._screen_bounds()
        width = max(1, right - left)
        height = max(1, bottom - top)
        x = round((point[0] - left) * 4095 / width)
        y = round((point[1] - top) * 4095 / height)
        return min(4095, max(0, x)), min(4095, max(0, y))

    def _require_client(self) -> WirelessHidClient:
        if not self.connected or self._client is None:
            raise WirelessHidError("Wireless HID controller is not connected")
        return self._client

    @staticmethod
    def _button_mask(button: str) -> int:
        try:
            return _BUTTONS[str(button).strip().lower()]
        except KeyError as exc:
            raise ValueError(f"unsupported mouse button: {button}") from exc

    @staticmethod
    def _resolve_key(key: str) -> tuple[int, int]:
        if len(key) == 1:
            return ascii_keystroke(key)
        normalized = key.strip().upper().replace("_", "").replace("-", "")
        try:
            return 0, _SPECIAL_KEYS[normalized]
        except KeyError as exc:
            raise ValueError(f"unsupported key: {key}") from exc

    def _pause(self, minimum: float, maximum: float) -> None:
        self._sleep(self._random.uniform(minimum, maximum))

    def _release_safely(self) -> None:
        try:
            if self._client is not None and getattr(self._client, "connected", True):
                self._client.release_all()
        except Exception:
            pass

    def _fail(self, action: str, started: float, error: Exception) -> bool:
        if self._client is None or not getattr(self._client, "connected", True):
            self._connected = False
        self._finish(action, False, started, error)
        return False

    def _finish(
        self,
        action: str,
        success: bool,
        started: float,
        error: Optional[Exception] = None,
    ) -> None:
        self._feedback_sequence += 1
        feedback = CommandFeedback(
            sequence=self._feedback_sequence,
            action=action,
            success=success,
            duration_ms=max(0, round((time.monotonic() - started) * 1000)),
            completed_at=time.time(),
            error="" if error is None else str(error),
        )
        self._last_feedback = feedback
        if self._feedback_callback is not None:
            try:
                self._feedback_callback(feedback)
            except Exception:
                pass
