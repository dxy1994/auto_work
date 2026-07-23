"""游戏脚本统一使用的拟人化键鼠输入层。

业务执行器只依赖 :class:`HumanizedInputController`，底层设备只需要实现
``mouse_move/mouse_click/mouse_drag/key_press/key_combo`` 这组稳定接口。
以后接入新的硬件安装包时，应新增或替换底层适配器，而不是修改游戏流程。
"""

from __future__ import annotations

import random
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional, Protocol, Sequence


ScreenBounds = tuple[int, int, int, int]


class InputDeviceAdapter(Protocol):
    """硬件安装包需要适配的最小设备接口。"""

    def mouse_move(
        self,
        x: int,
        y: int,
        trajectory: str = "human",
        jitter_x: int = 0,
        jitter_y: int = 0,
    ) -> bool: ...

    def mouse_click(self, button: str = "left") -> bool: ...

    def mouse_drag(self, x1: int, y1: int, x2: int, y2: int) -> bool: ...

    def key_press(self, key: str, duration_ms: int = 100) -> bool: ...

    def key_combo(self, keys: list[str], duration_ms: int = 100) -> bool: ...


@dataclass(frozen=True)
class HumanizationPolicy:
    """所有变化都限制在明确范围内，避免落点或时序不可控。"""

    click_radius_x: int = 3
    click_radius_y: int = 3
    drag_start_radius: int = 2
    drag_end_radius: int = 6
    before_action_seconds: tuple[float, float] = (0.04, 0.14)
    pointer_settle_seconds: tuple[float, float] = (0.06, 0.18)
    after_action_seconds: tuple[float, float] = (0.03, 0.12)
    double_click_interval_seconds: tuple[float, float] = (0.09, 0.16)
    key_hold_ms: tuple[int, int] = (55, 125)
    key_gap_seconds: tuple[float, float] = (0.035, 0.13)

    def __post_init__(self) -> None:
        for name in (
            "click_radius_x",
            "click_radius_y",
            "drag_start_radius",
            "drag_end_radius",
        ):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be non-negative")
        for name in (
            "before_action_seconds",
            "pointer_settle_seconds",
            "after_action_seconds",
            "double_click_interval_seconds",
            "key_hold_ms",
            "key_gap_seconds",
        ):
            low, high = getattr(self, name)
            if low < 0 or high < low:
                raise ValueError(f"invalid range for {name}: {(low, high)}")


DEFAULT_HUMANIZATION_POLICY = HumanizationPolicy()


class HumanizedInputController:
    """生成有界随机动作，并将最终动作交给当前硬件适配器执行。

    同一目标的连续动作会主动避开上一次实际落点。公共方法会串行执行，
    防止心跳检查、交易任务等不同线程把一个完整手势相互穿插。
    """

    def __init__(
        self,
        device: InputDeviceAdapter,
        *,
        policy: HumanizationPolicy = DEFAULT_HUMANIZATION_POLICY,
        random_source: Optional[random.Random] = None,
        sleep: Callable[[float], None] = time.sleep,
        cancelled: Optional[Callable[[], bool]] = None,
    ) -> None:
        self.device = device
        self.policy = policy
        self._random = random_source or random.Random()
        self._sleep = sleep
        self._cancelled = cancelled or (lambda: False)
        self._lock = threading.RLock()
        self._last_points: dict[tuple[object, ...], tuple[int, int]] = {}

    def move_to(
        self,
        x: int,
        y: int,
        *,
        radius_x: Optional[int] = None,
        radius_y: Optional[int] = None,
        bounds: Optional[ScreenBounds] = None,
    ) -> bool:
        """拟人化移动到目标附近，返回底层设备的执行结果。"""
        with self._lock:
            if self._is_cancelled():
                return False
            actual = self._vary_point(
                "move",
                int(x),
                int(y),
                self.policy.click_radius_x if radius_x is None else int(radius_x),
                self.policy.click_radius_y if radius_y is None else int(radius_y),
                bounds,
            )
            self._random_sleep(self.policy.before_action_seconds)
            if self._is_cancelled():
                return False
            return self._move_device(*actual)

    def click_at(
        self,
        x: int,
        y: int,
        *,
        button: str = "left",
        radius_x: Optional[int] = None,
        radius_y: Optional[int] = None,
        bounds: Optional[ScreenBounds] = None,
        clicks: int = 1,
    ) -> bool:
        """移动并点击目标附近；实际落点始终位于半径和边界交集内。"""
        if clicks < 1:
            raise ValueError("clicks must be at least 1")
        with self._lock:
            if self._is_cancelled():
                return False
            actual = self._vary_point(
                "click",
                int(x),
                int(y),
                self.policy.click_radius_x if radius_x is None else int(radius_x),
                self.policy.click_radius_y if radius_y is None else int(radius_y),
                bounds,
            )
            self._random_sleep(self.policy.before_action_seconds)
            if self._is_cancelled():
                return False
            if not self._move_device(*actual):
                return False
            self._random_sleep(self.policy.pointer_settle_seconds)
            for index in range(clicks):
                if self._is_cancelled() or self._click_device(button) is False:
                    return False
                if index + 1 < clicks:
                    self._random_sleep(self.policy.double_click_interval_seconds)
            self._random_sleep(self.policy.after_action_seconds)
            print(
                f"[INPUT] click target=({int(x)},{int(y)}) actual={actual} "
                f"button={button} clicks={clicks}"
            )
            return True

    def drag(
        self,
        start: tuple[int, int],
        end: tuple[int, int],
        *,
        start_radius: Optional[int] = None,
        end_radius: Optional[int] = None,
        bounds: Optional[ScreenBounds] = None,
    ) -> bool:
        """在起点和终点附近分别取有界变化点，并执行拟人化拖拽。"""
        with self._lock:
            if self._is_cancelled():
                return False
            sr = self.policy.drag_start_radius if start_radius is None else int(start_radius)
            er = self.policy.drag_end_radius if end_radius is None else int(end_radius)
            actual_start = self._vary_point(
                "drag_start", int(start[0]), int(start[1]), sr, sr, bounds
            )
            actual_end = self._vary_point(
                "drag_end", int(end[0]), int(end[1]), er, er, bounds
            )
            self._random_sleep(self.policy.before_action_seconds)
            if self._is_cancelled():
                return False
            if self.device.mouse_drag(*actual_start, *actual_end) is False:
                return False
            self._random_sleep(self.policy.after_action_seconds)
            print(
                f"[INPUT] drag target={start}->{end} "
                f"actual={actual_start}->{actual_end}"
            )
            return True

    def type_text(self, text: object) -> bool:
        """按逐字符变化的按压时长和字符间隔输入文本。"""
        value = str(text)
        if not value:
            return True
        with self._lock:
            if self._is_cancelled():
                return False
            plan = [
                {
                    "key": char,
                    "hold_ms": self._random.randint(*self.policy.key_hold_ms),
                    "gap_ms": round(
                        self._random.uniform(*self.policy.key_gap_seconds) * 1000
                    ),
                }
                for char in value
            ]
            bulk = getattr(self.device, "key_type_plan", None)
            if callable(bulk):
                success = bulk(value, plan)
            else:
                success = self._execute_typing_plan(plan)
            if success is False:
                return False
            print(
                f"[INPUT] type_text length={len(value)} "
                f"hold_ms={self.policy.key_hold_ms} gap={self.policy.key_gap_seconds}"
            )
            return True

    def press_key(self, key: str) -> bool:
        """以有界随机按压时长执行单键。"""
        with self._lock:
            if self._is_cancelled():
                return False
            self._random_sleep(self.policy.before_action_seconds)
            if self._is_cancelled():
                return False
            hold_ms = self._random.randint(*self.policy.key_hold_ms)
            if self.device.key_press(str(key), duration_ms=hold_ms) is False:
                return False
            self._random_sleep(self.policy.after_action_seconds)
            print(f"[INPUT] press_key key={key} hold_ms={hold_ms}")
            return True

    def press_combo(self, keys: Sequence[str]) -> bool:
        """以有界随机按压时长执行组合键。"""
        normalized = [str(key) for key in keys]
        if not normalized:
            raise ValueError("keys must not be empty")
        with self._lock:
            if self._is_cancelled():
                return False
            self._random_sleep(self.policy.before_action_seconds)
            if self._is_cancelled():
                return False
            hold_ms = self._random.randint(*self.policy.key_hold_ms)
            if self.device.key_combo(normalized, duration_ms=hold_ms) is False:
                return False
            self._random_sleep(self.policy.after_action_seconds)
            print(f"[INPUT] press_combo keys={normalized} hold_ms={hold_ms}")
            return True

    def _execute_typing_plan(self, plan: list[dict[str, object]]) -> bool:
        for item in plan:
            if self._is_cancelled():
                return False
            if self.device.key_press(
                str(item["key"]), duration_ms=int(item["hold_ms"])
            ) is False:
                return False
            self._sleep(max(0, int(item["gap_ms"])) / 1000.0)
        return True

    def _move_device(self, x: int, y: int) -> bool:
        try:
            result = self.device.mouse_move(
                x, y, trajectory="human", jitter_x=0, jitter_y=0
            )
        except TypeError:
            # 兼容暂未接受轨迹参数的设备安装包；正式接入时可在适配器内消除此分支。
            result = self.device.mouse_move(x, y)
        return result is not False

    def _click_device(self, button: str) -> bool:
        try:
            result = self.device.mouse_click(button=button)
        except TypeError:
            if button != "left":
                return False
            # 兼容旧安装包只提供无参数左键点击的情况。
            result = self.device.mouse_click()
        return result is not False

    def _vary_point(
        self,
        action: str,
        x: int,
        y: int,
        radius_x: int,
        radius_y: int,
        bounds: Optional[ScreenBounds],
    ) -> tuple[int, int]:
        if radius_x < 0 or radius_y < 0:
            raise ValueError("point radius must be non-negative")
        min_x, max_x = x - radius_x, x + radius_x
        min_y, max_y = y - radius_y, y + radius_y
        if bounds is not None:
            left, top, right, bottom = (int(value) for value in bounds)
            if right < left or bottom < top:
                raise ValueError(f"invalid screen bounds: {bounds}")
            min_x, max_x = max(min_x, left), min(max_x, right)
            min_y, max_y = max(min_y, top), min(max_y, bottom)
        if min_x > max_x or min_y > max_y:
            raise ValueError(
                f"target ({x}, {y}) and radius do not intersect bounds {bounds}"
            )

        key = (action, x, y, radius_x, radius_y, bounds)
        previous = self._last_points.get(key)
        point = (
            self._random.randint(min_x, max_x),
            self._random.randint(min_y, max_y),
        )
        if point == previous and (min_x < max_x or min_y < max_y):
            # 即使随机源连续给出相同值，也保证相同动作不连续落在同一像素。
            if point[0] < max_x:
                point = (point[0] + 1, point[1])
            elif point[0] > min_x:
                point = (point[0] - 1, point[1])
            elif point[1] < max_y:
                point = (point[0], point[1] + 1)
            else:
                point = (point[0], point[1] - 1)
        self._last_points[key] = point
        return point

    def _random_sleep(self, seconds_range: tuple[float, float]) -> None:
        if self._is_cancelled():
            return
        low, high = seconds_range
        self._sleep(self._random.uniform(low, high))

    def _is_cancelled(self) -> bool:
        return bool(self._cancelled())
