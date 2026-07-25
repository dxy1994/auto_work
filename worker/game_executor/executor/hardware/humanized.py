"""游戏脚本统一使用的拟人化键鼠输入层。

业务执行器只依赖 :class:`HumanizedInputController`，底层设备只需要实现
``mouse_move/mouse_click/mouse_drag/key_press/key_combo`` 这组稳定接口。
以后接入新的硬件安装包时，应新增或替换底层适配器，而不是修改游戏流程。
"""

from __future__ import annotations

import json
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
        self._action_visualizer: Optional[Callable[[dict[str, object]], object]] = None

    def set_action_visualizer(
        self,
        visualizer: Optional[Callable[[dict[str, object]], object]],
    ) -> None:
        """设置点击前的可视化回调；失败只记日志，不中断游戏流程。"""
        self._action_visualizer = visualizer

    def move_to(
        self,
        x: int,
        y: int,
        *,
        radius_x: Optional[int] = None,
        radius_y: Optional[int] = None,
        bounds: Optional[ScreenBounds] = None,
        coordinate_origin: Optional[tuple[int, int]] = None,
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
            coordinate_details = self._point_coordinate_details(
                (int(x), int(y)),
                actual,
                coordinate_origin,
            )
            self._log_action(
                "mouse_move",
                self._point_instruction("移动鼠标到", actual, coordinate_details),
                target=[int(x), int(y)],
                actual=list(actual),
                coordinate_space="screen_absolute",
                **coordinate_details,
            )
            self._random_sleep(self.policy.before_action_seconds)
            if self._is_cancelled():
                return False
            self._set_device_coordinate_context(coordinate_details)
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
        coordinate_origin: Optional[tuple[int, int]] = None,
    ) -> bool:
        """移动并点击目标附近；实际落点始终位于半径和边界交集内。"""
        if clicks < 1:
            raise ValueError("clicks must be at least 1")
        with self._lock:
            if self._is_cancelled():
                return False
            resolved_radius_x = (
                self.policy.click_radius_x
                if radius_x is None
                else int(radius_x)
            )
            resolved_radius_y = (
                self.policy.click_radius_y
                if radius_y is None
                else int(radius_y)
            )
            action_bounds = self._effective_point_bounds(
                int(x),
                int(y),
                resolved_radius_x,
                resolved_radius_y,
                bounds,
            )
            actual = self._vary_point(
                "click",
                int(x),
                int(y),
                resolved_radius_x,
                resolved_radius_y,
                bounds,
            )
            coordinate_details = self._point_coordinate_details(
                (int(x), int(y)),
                actual,
                coordinate_origin,
                action_bounds,
            )
            client_actual = coordinate_details.get("client_actual")
            client_origin = coordinate_details.get("client_origin")
            client_action_bounds = coordinate_details.get("client_action_bounds")
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
                    f"在游戏客户区坐标 ({client_actual[0]},{client_actual[1]}) "
                    f"执行{button}键点击"
                    f"（屏幕绝对坐标 ({actual[0]},{actual[1]})；"
                    f"客户区原点 ({client_origin[0]},{client_origin[1]})"
                    f"{action_range_text}）"
                )
            else:
                instruction = (
                    f"在屏幕绝对坐标 ({actual[0]},{actual[1]}) "
                    f"执行{button}键点击"
                )
            self._log_action(
                "mouse_click",
                instruction,
                target=[int(x), int(y)],
                actual=list(actual),
                coordinate_space="screen_absolute",
                button=button,
                clicks=clicks,
                **coordinate_details,
            )
            self._random_sleep(self.policy.before_action_seconds)
            if self._is_cancelled():
                return False
            self._set_device_coordinate_context(coordinate_details)
            if not self._move_device(*actual):
                return False
            self._random_sleep(self.policy.pointer_settle_seconds)
            for index in range(clicks):
                if self._is_cancelled() or self._click_device(button) is False:
                    return False
                if index + 1 < clicks:
                    self._random_sleep(self.policy.double_click_interval_seconds)
            self._random_sleep(self.policy.after_action_seconds)
            return True

    def drag(
        self,
        start: tuple[int, int],
        end: tuple[int, int],
        *,
        start_radius: Optional[int] = None,
        end_radius: Optional[int] = None,
        bounds: Optional[ScreenBounds] = None,
        coordinate_origin: Optional[tuple[int, int]] = None,
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
            start_action_bounds = self._effective_point_bounds(
                int(start[0]),
                int(start[1]),
                sr,
                sr,
                bounds,
            )
            end_action_bounds = self._effective_point_bounds(
                int(end[0]),
                int(end[1]),
                er,
                er,
                bounds,
            )
            coordinate_details = self._drag_coordinate_details(
                start,
                end,
                actual_start,
                actual_end,
                coordinate_origin,
                start_action_bounds,
                end_action_bounds,
            )
            client_actual_start = coordinate_details.get("client_actual_start")
            client_actual_end = coordinate_details.get("client_actual_end")
            client_origin = coordinate_details.get("client_origin")
            if (
                isinstance(client_actual_start, list)
                and isinstance(client_actual_end, list)
                and isinstance(client_origin, list)
            ):
                instruction = (
                    f"从游戏客户区坐标 ({client_actual_start[0]},{client_actual_start[1]}) "
                    f"拖拽到 ({client_actual_end[0]},{client_actual_end[1]})"
                    f"（屏幕绝对坐标 ({actual_start[0]},{actual_start[1]}) "
                    f"到 ({actual_end[0]},{actual_end[1]})；"
                    f"客户区原点 ({client_origin[0]},{client_origin[1]})）"
                )
            else:
                instruction = (
                    f"从屏幕绝对坐标 ({actual_start[0]},{actual_start[1]}) "
                    f"拖拽到 ({actual_end[0]},{actual_end[1]})"
                )
            self._log_action(
                "mouse_drag",
                instruction,
                target_start=list(start),
                target_end=list(end),
                actual_start=list(actual_start),
                actual_end=list(actual_end),
                coordinate_space="screen_absolute",
                **coordinate_details,
            )
            self._random_sleep(self.policy.before_action_seconds)
            if self._is_cancelled():
                return False
            self._set_device_coordinate_context(coordinate_details)
            if self.device.mouse_drag(*actual_start, *actual_end) is False:
                return False
            self._random_sleep(self.policy.after_action_seconds)
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
            self._log_action(
                "key_type",
                f"输入文字：{value}",
                text=value,
                typing_plan=plan,
            )
            bulk = getattr(self.device, "key_type_plan", None)
            if callable(bulk):
                success = bulk(value, plan)
            else:
                success = self._execute_typing_plan(plan)
            if success is False:
                return False
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
            self._log_action(
                "key_press",
                f"按键：{key}",
                key=str(key),
                hold_ms=hold_ms,
            )
            if self.device.key_press(str(key), duration_ms=hold_ms) is False:
                return False
            self._random_sleep(self.policy.after_action_seconds)
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
            self._log_action(
                "key_combo",
                "组合键：" + "+".join(normalized),
                keys=normalized,
                hold_ms=hold_ms,
            )
            if self.device.key_combo(normalized, duration_ms=hold_ms) is False:
                return False
            self._random_sleep(self.policy.after_action_seconds)
            return True

    def _log_action(self, action: str, instruction: str, **details: object) -> None:
        """在动作发送到硬件前输出完整、可直接人工执行的信息。"""
        payload: dict[str, object] = {
            "action": action,
            "phase": "planned",
            "instruction": instruction,
            "execution_mode": (
                "manual" if getattr(self.device, "manual_mode", False) else "hardware"
            ),
            **details,
        }
        visualized_actions = {
            "mouse_click",
            "mouse_drag",
            "key_type",
            "key_press",
            "key_combo",
        }
        if action in visualized_actions and callable(self._action_visualizer):
            try:
                image_path = self._action_visualizer(dict(payload))
                if image_path:
                    payload["visual_debug_image"] = str(image_path)
                    print(
                        f"[GAME-ACTION-VISUAL] {image_path}",
                        flush=True,
                    )
            except Exception as exc:
                print(
                    f"[GAME-ACTION-VISUAL] 生成操作标注图失败: {exc}",
                    flush=True,
                )
        print(
            "[GAME-ACTION] "
            + json.dumps(
                payload,
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            flush=True,
        )

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

    @staticmethod
    def _point_coordinate_details(
        target: tuple[int, int],
        actual: tuple[int, int],
        coordinate_origin: Optional[tuple[int, int]],
        action_bounds: Optional[ScreenBounds] = None,
    ) -> dict[str, object]:
        details: dict[str, object] = {}
        if action_bounds is not None:
            details["screen_action_bounds"] = list(action_bounds)
        if coordinate_origin is None:
            return details
        ox, oy = (int(value) for value in coordinate_origin)
        details.update({
            "client_origin": [ox, oy],
            "client_target": [target[0] - ox, target[1] - oy],
            "client_actual": [actual[0] - ox, actual[1] - oy],
            "screen_target": list(target),
            "screen_actual": list(actual),
        })
        if action_bounds is not None:
            left, top, right, bottom = action_bounds
            details["client_action_bounds"] = [
                left - ox,
                top - oy,
                right - ox,
                bottom - oy,
            ]
        return details

    @staticmethod
    def _drag_coordinate_details(
        target_start: tuple[int, int],
        target_end: tuple[int, int],
        actual_start: tuple[int, int],
        actual_end: tuple[int, int],
        coordinate_origin: Optional[tuple[int, int]],
        start_action_bounds: Optional[ScreenBounds] = None,
        end_action_bounds: Optional[ScreenBounds] = None,
    ) -> dict[str, object]:
        details: dict[str, object] = {}
        if start_action_bounds is not None:
            details["screen_start_action_bounds"] = list(start_action_bounds)
        if end_action_bounds is not None:
            details["screen_end_action_bounds"] = list(end_action_bounds)
        if coordinate_origin is None:
            return details
        ox, oy = (int(value) for value in coordinate_origin)
        details.update({
            "client_origin": [ox, oy],
            "client_target_start": [target_start[0] - ox, target_start[1] - oy],
            "client_target_end": [target_end[0] - ox, target_end[1] - oy],
            "client_actual_start": [actual_start[0] - ox, actual_start[1] - oy],
            "client_actual_end": [actual_end[0] - ox, actual_end[1] - oy],
            "screen_target_start": list(target_start),
            "screen_target_end": list(target_end),
            "screen_actual_start": list(actual_start),
            "screen_actual_end": list(actual_end),
        })
        if start_action_bounds is not None:
            left, top, right, bottom = start_action_bounds
            details["client_start_action_bounds"] = [
                left - ox,
                top - oy,
                right - ox,
                bottom - oy,
            ]
        if end_action_bounds is not None:
            left, top, right, bottom = end_action_bounds
            details["client_end_action_bounds"] = [
                left - ox,
                top - oy,
                right - ox,
                bottom - oy,
            ]
        return details

    @staticmethod
    def _point_instruction(
        prefix: str,
        actual: tuple[int, int],
        coordinate_details: dict[str, object],
    ) -> str:
        client_actual = coordinate_details.get("client_actual")
        client_origin = coordinate_details.get("client_origin")
        if isinstance(client_actual, list) and isinstance(client_origin, list):
            return (
                f"{prefix}游戏客户区坐标 ({client_actual[0]},{client_actual[1]})"
                f"（屏幕绝对坐标 ({actual[0]},{actual[1]})；"
                f"客户区原点 ({client_origin[0]},{client_origin[1]})）"
            )
        return f"{prefix}屏幕绝对坐标 ({actual[0]},{actual[1]})"

    def _set_device_coordinate_context(
        self,
        coordinate_details: dict[str, object],
    ) -> None:
        setter = getattr(self.device, "set_coordinate_context", None)
        if callable(setter):
            setter(coordinate_details)

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
        min_x, min_y, max_x, max_y = self._effective_point_bounds(
            x,
            y,
            radius_x,
            radius_y,
            bounds,
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

    @staticmethod
    def _effective_point_bounds(
        x: int,
        y: int,
        radius_x: int,
        radius_y: int,
        bounds: Optional[ScreenBounds],
    ) -> ScreenBounds:
        """返回目标半径与外部边界求交后的真实随机落点范围（边界均包含）。"""
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
        return min_x, min_y, max_x, max_y

    def _random_sleep(self, seconds_range: tuple[float, float]) -> None:
        if self._is_cancelled():
            return
        low, high = seconds_range
        self._sleep(self._random.uniform(low, high))

    def _is_cancelled(self) -> bool:
        return bool(self._cancelled())
