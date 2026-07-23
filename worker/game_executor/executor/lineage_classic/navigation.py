"""Lineage Classic 800x600 客户端的登录、切区与物品栏前置检查。"""

from __future__ import annotations

import base64
import binascii
import math
import os
import random
import re
import sys
import time
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Callable, Optional, Protocol
from urllib.error import URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from common.config import BACKEND_WS_URL

from game_executor.executor.hardware.humanized import HumanizedInputController
from game_executor.executor.lineage_classic.paddle_ocr import (
    recognize_korean,
    recognize_korean_boxes,
)

try:
    import cv2
    import numpy as np
    from PIL import ImageGrab
except ImportError:  # 单元测试和未安装 Trader 图像依赖的环境
    cv2 = None
    np = None
    ImageGrab = None

try:
    import win32con
    import win32gui
except ImportError:
    win32con = None
    win32gui = None


CLIENT_SIZE = (800, 600)
OCR_MIN_CONFIDENCE = min(
    100.0,
    max(90.0, float(os.getenv("LINEAGE_OCR_MIN_CONFIDENCE", "90"))),
)
REGION_TEXT_SIMILARITY = min(
    1.0,
    max(0.90, float(os.getenv("LINEAGE_REGION_TEXT_SIMILARITY", "0.90"))),
)
WINDOW_TITLE_RE = re.compile(
    r"^Lineage Classic - (?P<version>.+?) \[LIVE\] - Login \[(?P<account>.+?)\]",
    re.IGNORECASE,
)

STEP_VERIFY_ATTEMPTS = 3


@dataclass(frozen=True)
class StepWaitProfile:
    label: str
    fixed_wait: float
    random_min: float
    random_max: float
    probe_interval: float


STEP_WAIT_PROFILES = {
    # 大区、选角、登录和交易窗口等整幅画面变化需要给客户端充分加载时间。
    "screen": StepWaitProfile("画面切换", 3.0, 3.0, 10.0, 2.0),
    # 菜单展开、按钮出现等局部 UI 变化。
    "panel": StepWaitProfile("面板操作", 0.8, 1.5, 4.0, 1.0),
    # OCR/模板识别可能受一两帧渲染影响，但不需要按整幅画面等待。
    "recognition": StepWaitProfile("图像识别", 0.5, 1.0, 3.0, 0.8),
    # 拖拽和键盘输入保持短暂停顿，避免显得机械，同时不拖慢多物品订单。
    "item_drag": StepWaitProfile("物品拖拽", 0.2, 0.3, 1.2, 0.4),
    "input": StepWaitProfile("数量输入", 0.3, 0.4, 1.5, 0.4),
    # 最终交易结果需要比普通按钮更谨慎地确认。
    "final_verify": StepWaitProfile("结果验证", 2.0, 3.0, 8.0, 0.5),
}


class Ui:
    INVENTORY_REGION = (600, 10, 762, 330)
    CHARACTER_PICK_REGION = (136, 57, 225, 294)
    CHARACTER_ACTION_REGION = (17, 340, 464, 414)
    CHARACTER_SELECTED_PIXEL = (166, 311)
    SYSTEM_REGION = (600, 10, 783, 234)
    SERVER_REGION = (220, 107, 560, 430)
    FULL_CLIENT = (0, 0, 800, 600)

    INVENTORY_BUTTON = "物品栏按钮.png"
    MENU_BUTTON = "切换菜单按钮.png"
    EXIT_PANEL_TRIGGER = "退出登录界面触发按钮.png"
    RELOGIN_BUTTON = "重新登录按钮.png"
    CHARACTER_SCREEN = "选人界面判断.png"
    CHARACTER_EXIT = "选人界面退出登录按钮.png"
    CHARACTER_LOGIN = "选人界面登录按钮.png"
    SERVER_SCREEN = "选择服务器界面判断.png"
    SERVER_CONFIRM = "选中大区后的确认按钮.png"


class NavigationError(RuntimeError):
    pass


class NavigationCancelled(NavigationError):
    pass


@dataclass(frozen=True)
class TargetRegion:
    region_id: int
    name: str
    code: str
    select_x: Optional[int]
    select_y: Optional[int]
    select_page: int = 1
    sort_order: int = 0

    @classmethod
    def from_order(cls, order: dict) -> "TargetRegion":
        try:
            raw_x = order.get("region_select_x")
            raw_y = order.get("region_select_y")
            raw_page = order.get("region_select_page")
            if (raw_x is None) != (raw_y is None):
                raise NavigationError("后台订单的大区选择坐标 X、Y 必须同时提供")
            target = cls(
                region_id=int(order["region_id"]),
                name=str(order.get("region_name") or "").strip(),
                code=str(order.get("region_code") or "").strip(),
                select_x=int(raw_x) if raw_x is not None else None,
                select_y=int(raw_y) if raw_y is not None else None,
                select_page=int(raw_page) if raw_page is not None else 1,
                sort_order=int(order.get("region_sort_order") or 0),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise NavigationError("后台订单缺少有效的大区定位信息") from exc
        if target.region_id <= 0:
            raise NavigationError("后台订单的大区 ID 无效")
        if target.select_page < 1:
            raise NavigationError("后台订单的大区页码必须大于或等于 1")
        if target.select_x is not None and not (
            0 <= target.select_x < CLIENT_SIZE[0]
            and 0 <= target.select_y < CLIENT_SIZE[1]
        ):
            raise NavigationError("后台订单的大区选择坐标超出 800x600 客户区")
        if not target.name and not target.code:
            raise NavigationError("后台订单缺少大区名称和代码")
        return target


class ClientWindow:
    def __init__(self, hwnd: int, title: str):
        self.hwnd = hwnd
        self.title = title

    @property
    def account(self) -> str:
        match = WINDOW_TITLE_RE.search(self.title)
        return match.group("account") if match else ""

    @classmethod
    def find(cls, account: str = "") -> "ClientWindow":
        if win32gui is None:
            raise NavigationError("当前环境未安装 pywin32，无法查找游戏窗口")
        candidates: list[tuple[int, str]] = []

        def collect(hwnd: int, _extra) -> None:
            if not win32gui.IsWindowVisible(hwnd):
                return
            title = win32gui.GetWindowText(hwnd)
            match = WINDOW_TITLE_RE.search(title)
            if match and (not account or match.group("account").casefold() == account.casefold()):
                candidates.append((hwnd, title))

        win32gui.EnumWindows(collect, None)
        if not candidates:
            suffix = f"（账号 {account}）" if account else ""
            raise NavigationError(f"未找到 Lineage Classic [LIVE] 登录窗口{suffix}")
        if len(candidates) > 1 and not account:
            raise NavigationError("检测到多个游戏窗口，必须提供游戏登录账号以避免操作错窗口")
        return cls(*candidates[0])

    def _try_activate(self) -> None:
        """恢复请求后立即激活窗口，促使游戏重新创建渲染客户区。"""
        for action_name in ("BringWindowToTop", "SetForegroundWindow"):
            action = getattr(win32gui, action_name, None)
            if callable(action):
                try:
                    action(self.hwnd)
                except Exception:
                    pass

    def _wait_for_restored_size(self, timeout: float) -> tuple[int, int]:
        deadline = time.monotonic() + max(0.0, timeout)
        while True:
            size = self.client_size()
            if size != (0, 0) and not win32gui.IsIconic(self.hwnd):
                return size
            if time.monotonic() >= deadline:
                return size
            time.sleep(0.1)

    def restore(self, timeout: float = 5.0) -> tuple[int, int]:
        """通过多种 Win32 方式恢复最小化窗口，并等待客户区重新可用。"""
        size = self.client_size()
        if not win32gui.IsIconic(self.hwnd) and size != (0, 0):
            return size

        wm_syscommand = getattr(win32con, "WM_SYSCOMMAND", 0x0112)
        sc_restore = getattr(win32con, "SC_RESTORE", 0xF120)
        attempts: list[tuple[str, Callable[[], object]]] = []
        show_async = getattr(win32gui, "ShowWindowAsync", None)
        if callable(show_async):
            attempts.append((
                "ShowWindowAsync",
                lambda: show_async(self.hwnd, win32con.SW_RESTORE),
            ))
        post_message = getattr(win32gui, "PostMessage", None)
        if callable(post_message):
            attempts.append((
                "PostMessage(SC_RESTORE)",
                lambda: post_message(self.hwnd, wm_syscommand, sc_restore, 0),
            ))
        show_window = getattr(win32gui, "ShowWindow", None)
        if callable(show_window):
            attempts.append((
                "ShowWindow",
                lambda: show_window(self.hwnd, win32con.SW_RESTORE),
            ))

        errors: list[str] = []
        wait_per_attempt = max(0.2, timeout / max(1, len(attempts)))
        for name, request_restore in attempts:
            try:
                request_restore()
                self._try_activate()
                size = self._wait_for_restored_size(wait_per_attempt)
                if size != (0, 0) and not win32gui.IsIconic(self.hwnd):
                    print(f"[Lineage] 游戏窗口已通过 {name} 恢复")
                    return size
            except Exception as exc:
                errors.append(f"{name}: {exc}")

        detail = "；".join(errors)
        suffix = f"（{detail}）" if detail else ""
        raise NavigationError(
            "游戏窗口保持最小化，客户区仍为 0x0；"
            "如果游戏以管理员身份运行，请同样以管理员身份运行 game_executor"
            f"{suffix}"
        )

    def focus(self) -> None:
        size = self.restore()
        if size == (0, 0):
            raise NavigationError("游戏窗口仍处于最小化状态，自动恢复后客户区暂时为 0x0")
        try:
            win32gui.SetForegroundWindow(self.hwnd)
        except Exception as exc:
            raise NavigationError(f"游戏窗口已恢复，但无法切换到前台: {exc}") from exc
        time.sleep(0.3)

    def client_origin(self) -> tuple[int, int]:
        return win32gui.ClientToScreen(self.hwnd, (0, 0))

    def client_size(self) -> tuple[int, int]:
        left, top, right, bottom = win32gui.GetClientRect(self.hwnd)
        return right - left, bottom - top

    def validate_size(self, size: Optional[tuple[int, int]] = None) -> None:
        size = size or self.client_size()
        if size != CLIENT_SIZE:
            raise NavigationError(f"游戏客户区必须为 800x600，当前为 {size[0]}x{size[1]}")


class Vision(Protocol):
    def find(self, template: str, region: tuple[int, int, int, int], threshold: float = 0.84) -> Optional[tuple[int, int]]: ...
    def pixel(self, point: tuple[int, int]) -> tuple[int, int, int]: ...
    def read_text(self, region: tuple[int, int, int, int]) -> str: ...
    def find_text(self, target: TargetRegion, region: tuple[int, int, int, int]) -> Optional[tuple[int, int]]: ...
    def find_image(self, image_source: str, region: tuple[int, int, int, int], threshold: float = 0.90) -> Optional[tuple[int, int]]: ...


@dataclass(frozen=True)
class OcrResult:
    text: str
    confidence: float


class TemplateVision:
    def __init__(self, window: ClientWindow, image_dir: Optional[Path] = None):
        if cv2 is None or ImageGrab is None:
            raise NavigationError("未安装 opencv-python/Pillow，无法识别游戏界面")
        self.window = window
        self.image_dir = image_dir or Path(__file__).with_name("images")
        self._templates: dict[str, object] = {}
        self._dynamic_templates: dict[str, object] = {}
        self._ocr_warning_printed = False

    def _capture(self, region: tuple[int, int, int, int]):
        ox, oy = self.window.client_origin()
        left, top, right, bottom = region
        image = ImageGrab.grab(bbox=(ox + left, oy + top, ox + right, oy + bottom), all_screens=True)
        return cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)

    def _template(self, name: str):
        if name not in self._templates:
            path = self.image_dir / name
            try:
                encoded = np.fromfile(os.fspath(path), dtype=np.uint8)
                template = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
            except OSError:
                template = None
            if template is None:
                raise NavigationError(f"无法读取识别图片: {path}")
            self._templates[name] = template
        return self._templates[name]

    def find(self, template: str, region: tuple[int, int, int, int], threshold: float = 0.84) -> Optional[tuple[int, int]]:
        source = self._capture(region)
        needle = self._template(template)
        return self._match_template(source, needle, region, threshold)

    @staticmethod
    def _match_template(source, needle, region, threshold: float) -> Optional[tuple[int, int]]:
        height, width = needle.shape[:2]
        if source.shape[0] < height or source.shape[1] < width:
            return None
        result = cv2.matchTemplate(source, needle, cv2.TM_CCOEFF_NORMED)
        _, confidence, _, location = cv2.minMaxLoc(result)
        if confidence < threshold:
            return None
        return region[0] + location[0] + width // 2, region[1] + location[1] + height // 2

    @staticmethod
    def _absolute_image_url(image_source: str) -> str:
        parsed = urlparse(image_source)
        if parsed.scheme in {"http", "https"}:
            return image_source
        backend = urlparse(BACKEND_WS_URL)
        scheme = "https" if backend.scheme == "wss" else "http"
        return urljoin(f"{scheme}://{backend.netloc}/", image_source)

    def _dynamic_template(self, image_source: str):
        key = str(image_source or "").strip()
        if not key:
            raise NavigationError("订单物品缺少识别图片")
        if key in self._dynamic_templates:
            return self._dynamic_templates[key]
        try:
            if key.startswith("data:image/"):
                _header, payload = key.split(",", 1)
                raw = base64.b64decode(payload, validate=True)
            else:
                request = Request(
                    self._absolute_image_url(key),
                    headers={
                        "Accept": "image/*",
                        "User-Agent": "auto-game-executor/1.0",
                    },
                )
                with urlopen(request, timeout=8) as response:
                    content_type = response.headers.get_content_type()
                    if not content_type.startswith("image/"):
                        raise NavigationError(f"物品识别图片类型无效: {content_type}")
                    raw = response.read(1_048_577)
            if len(raw) > 1_048_576:
                raise NavigationError("物品识别图片超过 1MB")
            encoded = np.frombuffer(raw, dtype=np.uint8)
            template = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
        except NavigationError:
            raise
        except (OSError, URLError, ValueError, binascii.Error) as exc:
            raise NavigationError(f"加载物品识别图片失败: {key}") from exc
        if template is None:
            raise NavigationError(f"无法解码物品识别图片: {key}")
        self._dynamic_templates[key] = template
        return template

    def find_image(
        self,
        image_source: str,
        region: tuple[int, int, int, int],
        threshold: float = 0.90,
    ) -> Optional[tuple[int, int]]:
        source = self._capture(region)
        needle = self._dynamic_template(image_source)
        return self._match_template(source, needle, region, threshold)

    def pixel(self, point: tuple[int, int]) -> tuple[int, int, int]:
        x, y = point
        pixel = self._capture((x, y, x + 1, y + 1))[0, 0]
        return int(pixel[0]), int(pixel[1]), int(pixel[2])

    def capture_data_url(self, region: tuple[int, int, int, int]) -> str:
        success, encoded = cv2.imencode(".png", self._capture(region))
        if not success:
            raise NavigationError("交易申请截图编码失败")
        payload = base64.b64encode(encoded.tobytes()).decode("ascii")
        return f"data:image/png;base64,{payload}"

    def read_text(self, region: tuple[int, int, int, int]) -> str:
        result = self.read_text_result(region)
        return result.text if result.confidence >= OCR_MIN_CONFIDENCE else ""

    def read_text_result(self, region: tuple[int, int, int, int]) -> OcrResult:
        source = self._capture(region)
        scaled = cv2.resize(source, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
        enhanced = cv2.copyMakeBorder(
            scaled, 12, 12, 12, 12, cv2.BORDER_REPLICATE
        )
        try:
            text, confidence = recognize_korean(enhanced)
            if text and confidence >= OCR_MIN_CONFIDENCE:
                print(
                    f"[Lineage] PaddleOCR 韩语识别通过: text='{_printable(text)}' "
                    f"min_confidence={confidence:.1f}"
                )
            elif text:
                print(
                    f"[Lineage] PaddleOCR 韩语置信度不足: {confidence:.1f} "
                    f"< {OCR_MIN_CONFIDENCE:.1f}，转人工确认"
                )
            return OcrResult(text, confidence)
        except Exception as exc:
            if not self._ocr_warning_printed:
                print(f"[Lineage] PaddleOCR 不可用，将执行一次安全切区: {exc}")
                self._ocr_warning_printed = True
            return OcrResult("", -1.0)

    def find_text(
        self,
        target: TargetRegion,
        region: tuple[int, int, int, int],
    ) -> Optional[tuple[int, int]]:
        source = self._capture(region)
        scale = 4
        border = 12
        scaled = cv2.resize(source, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        enhanced = cv2.copyMakeBorder(
            scaled, border, border, border, border, cv2.BORDER_REPLICATE
        )
        try:
            boxes = recognize_korean_boxes(enhanced)
        except Exception as exc:
            if not self._ocr_warning_printed:
                print(f"[Lineage] PaddleOCR 不可用，无法按文字定位大区: {exc}")
                self._ocr_warning_printed = True
            return None
        for box in boxes:
            if box.confidence < OCR_MIN_CONFIDENCE or not region_text_matches(box.text, target):
                continue
            center_x, center_y = box.center
            point = (
                region[0] + int((center_x - border) / scale + 0.5),
                region[1] + int((center_y - border) / scale + 0.5),
            )
            print(
                f"[Lineage] OCR 定位大区 text='{_printable(box.text)}' "
                f"confidence={box.confidence:.1f} coordinate=({point[0]},{point[1]})"
            )
            return point
        return None


def _normalized_region(value: str) -> str:
    return "".join(ch.casefold() for ch in value if ch.isalnum())


def _printable(value: object) -> str:
    text = str(value)
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    return text.encode(encoding, errors="backslashreplace").decode(encoding)


def region_text_matches(text: str, target: TargetRegion) -> bool:
    actual = _normalized_region(text)
    if not actual:
        return False
    for alias in (target.name, target.code):
        expected = _normalized_region(alias)
        if not expected:
            continue
        if actual == expected:
            return True
        if SequenceMatcher(None, actual, expected).ratio() >= REGION_TEXT_SIMILARITY:
            return True
    return False


def item_recognition_images(detail: dict) -> tuple[str, str]:
    """返回未选中/选中两张识别图，兼容旧指令中的未选中图片字段。"""
    label = str(detail.get("item_name") or detail.get("item_id") or "未知物品")
    unselected = str(
        detail.get("recognition_image_unselected_url")
        or detail.get("recognition_image_url")
        or detail.get("item_image")
        or ""
    ).strip()
    selected = str(
        detail.get("recognition_image_selected_url")
        or detail.get("item_selected_image")
        or ""
    ).strip()
    if not unselected:
        raise NavigationError(f"物品 {label} 缺少未选中状态识别图片")
    if not selected:
        raise NavigationError(f"物品 {label} 缺少选中状态识别图片")
    return unselected, selected


class LineageSessionNavigator:
    def __init__(
        self,
        hardware,
        window: ClientWindow,
        vision: Vision,
        runtime_status=None,
        sleep: Callable[[float], None] = time.sleep,
        cancelled: Optional[Callable[[], bool]] = None,
        random_uniform: Callable[[float, float], float] = random.uniform,
        input_controller: Optional[HumanizedInputController] = None,
    ):
        self.hardware = hardware
        self.window = window
        self.vision = vision
        self.runtime_status = runtime_status
        self.sleep = sleep
        self.cancelled = cancelled or (lambda: False)
        self.random_uniform = random_uniform
        self.input = input_controller or HumanizedInputController(
            hardware,
            sleep=sleep,
            cancelled=self.cancelled,
        )

    def _screen_bounds(self) -> tuple[int, int, int, int]:
        ox, oy = self.window.client_origin()
        return ox, oy, ox + CLIENT_SIZE[0] - 1, oy + CLIENT_SIZE[1] - 1

    def _click(
        self,
        point: tuple[int, int],
        *,
        radius_x: Optional[int] = None,
        radius_y: Optional[int] = None,
    ) -> None:
        self._raise_if_cancelled()
        ox, oy = self.window.client_origin()
        x, y = point
        if self.input.click_at(
            ox + x,
            oy + y,
            radius_x=radius_x,
            radius_y=radius_y,
            bounds=self._screen_bounds(),
        ) is False:
            self._raise_if_cancelled()
            raise NavigationError(f"硬件点击失败: ({x}, {y})")

    def click(
        self,
        point: tuple[int, int],
        *,
        radius_x: Optional[int] = None,
        radius_y: Optional[int] = None,
    ) -> None:
        """在游戏客户区目标点附近执行有界变化点击。"""
        self._click(point, radius_x=radius_x, radius_y=radius_y)

    def click_region(self, region: tuple[int, int, int, int]) -> None:
        """在按钮区域内部变化落点，并保留边缘安全距离。"""
        left, top, right, bottom = region
        center = ((left + right) // 2, (top + bottom) // 2)
        radius_x = max(0, (right - left) // 2 - 2)
        radius_y = max(0, (bottom - top) // 2 - 2)
        self._click(center, radius_x=radius_x, radius_y=radius_y)

    def drag(self, start: tuple[int, int], end: tuple[int, int]) -> None:
        """按游戏客户区相对坐标执行起终点均有界变化的拖拽。"""
        self._raise_if_cancelled()
        ox, oy = self.window.client_origin()
        if self.input.drag(
            (ox + start[0], oy + start[1]),
            (ox + end[0], oy + end[1]),
            bounds=self._screen_bounds(),
        ) is False:
            self._raise_if_cancelled()
            raise NavigationError(f"硬件拖拽失败: {start} -> {end}")

    def type_text(self, text: object) -> None:
        """通过统一输入层拟人化输入文本。"""
        self._raise_if_cancelled()
        if self.input.type_text(text) is False:
            self._raise_if_cancelled()
            raise NavigationError("硬件文本输入失败")

    def press_key(self, key: str) -> None:
        """通过统一输入层拟人化执行单键。"""
        self._raise_if_cancelled()
        if self.input.press_key(key) is False:
            self._raise_if_cancelled()
            raise NavigationError(f"硬件按键失败: {key}")

    def _raise_if_cancelled(self) -> None:
        if self.cancelled():
            raise NavigationCancelled("交易已取消")

    def _find(self, template: str, region=Ui.FULL_CLIENT, threshold: float = 0.84):
        return self.vision.find(template, region, threshold)

    def _wait_for(self, predicate: Callable[[], object], timeout: float, interval: float = 0.5):
        attempts = max(1, math.ceil(timeout / interval))
        for _ in range(attempts):
            self._raise_if_cancelled()
            result = predicate()
            if result:
                return result
            self.sleep(interval)
        return None

    def _sleep_interruptibly(self, seconds: float) -> None:
        """按短片段等待，确保长步骤等待期间仍能及时响应取消。"""
        remaining = max(0.0, float(seconds))
        while remaining > 0:
            self._raise_if_cancelled()
            chunk = min(0.25, remaining)
            self.sleep(chunk)
            remaining -= chunk

    def wait_for_step(
        self,
        step_name: str,
        predicate: Callable[[], object],
        *,
        profile: str,
        fixed_wait: Optional[float] = None,
        attempts: int = STEP_VERIFY_ATTEMPTS,
        probe_interval: Optional[float] = None,
    ):
        """动作后先做人性化等待，再最多检测三次下一步状态。"""
        timing = STEP_WAIT_PROFILES.get(profile)
        if timing is None:
            raise ValueError(f"未知步骤等待类型: {profile}")
        fixed_seconds = max(0.0, float(
            timing.fixed_wait if fixed_wait is None else fixed_wait
        ))
        random_seconds = float(self.random_uniform(
            timing.random_min,
            timing.random_max,
        ))
        random_seconds = min(
            timing.random_max,
            max(timing.random_min, random_seconds),
        )
        total_wait = fixed_seconds + random_seconds
        max_attempts = max(1, int(attempts))
        check_interval = max(0.0, float(
            timing.probe_interval if probe_interval is None else probe_interval
        ))
        print(
            f"[Lineage][步骤等待] {step_name} [{timing.label}]: "
            f"固定 {fixed_seconds:.2f}s + 随机 {random_seconds:.2f}s "
            f"= {total_wait:.2f}s，随后最多检测 {max_attempts} 次"
        )
        self._sleep_interruptibly(total_wait)

        last_error = ""
        for attempt in range(1, max_attempts + 1):
            self._raise_if_cancelled()
            try:
                result = predicate()
                ready = result is not None and result is not False
            except NavigationCancelled:
                raise
            except Exception as exc:
                result = None
                ready = False
                last_error = str(exc)
            outcome = "已就绪" if ready else "未就绪"
            suffix = f"，检测异常={last_error}" if last_error else ""
            print(
                f"[Lineage][步骤检测] {step_name}: "
                f"第 {attempt}/{max_attempts} 次 {outcome}{suffix}"
            )
            if ready:
                return result
            if attempt < max_attempts:
                self._sleep_interruptibly(check_interval)

        detail = f"，最后异常={last_error}" if last_error else ""
        print(
            f"[Lineage][步骤失败] {step_name}: "
            f"连续 {max_attempts} 次检测均未达到下一步状态{detail}"
        )
        return None

    def wait_after_step(
        self,
        step_name: str,
        *,
        profile: str,
        fixed_wait: Optional[float] = None,
    ) -> None:
        """没有可靠视觉锚点的动作仍执行统一等待并记录一次完成检测。"""
        self.wait_for_step(
            step_name,
            lambda: True,
            profile=profile,
            fixed_wait=fixed_wait,
        )

    def _is_in_game(self) -> bool:
        return any((
            self._find(Ui.INVENTORY_BUTTON, Ui.INVENTORY_REGION) is not None,
            self._find(Ui.MENU_BUTTON, Ui.SYSTEM_REGION) is not None,
            self._find(Ui.EXIT_PANEL_TRIGGER, Ui.SYSTEM_REGION) is not None,
            self._find(Ui.RELOGIN_BUTTON, Ui.SYSTEM_REGION) is not None,
        ))

    def _is_character_screen(self) -> bool:
        return self._find(Ui.CHARACTER_SCREEN) is not None

    def _is_server_screen(self) -> bool:
        return self._find(Ui.SERVER_SCREEN, Ui.SERVER_REGION) is not None

    def _open_exit_panel_and_relogin(self) -> None:
        relogin = self._find(Ui.RELOGIN_BUTTON, Ui.SYSTEM_REGION)
        if relogin is None:
            trigger = self._find(Ui.EXIT_PANEL_TRIGGER, Ui.SYSTEM_REGION)
            if trigger is None:
                menu = self._find(Ui.MENU_BUTTON, Ui.SYSTEM_REGION)
                if menu is None:
                    menu = self.wait_for_step(
                        "查找切换菜单按钮",
                        lambda: self._find(Ui.MENU_BUTTON, Ui.SYSTEM_REGION),
                        profile="recognition",
                    )
                if menu is None:
                    raise NavigationError("连续 3 次未找到退出登录触发按钮或切换菜单按钮")
                self._click(menu)
                trigger = self.wait_for_step(
                    "打开切换菜单",
                    lambda: self._find(Ui.EXIT_PANEL_TRIGGER, Ui.SYSTEM_REGION),
                    profile="panel",
                )
            if trigger is None:
                raise NavigationError("打开切换菜单后仍未找到退出登录触发按钮")
            self._click(trigger)
            relogin = self.wait_for_step(
                "打开重新登录操作面板",
                lambda: self._find(Ui.RELOGIN_BUTTON, Ui.SYSTEM_REGION),
                profile="panel",
            )
        if relogin is None:
            raise NavigationError("未找到重新登录按钮")
        self._click(relogin)
        if not self.wait_for_step(
            "重新登录后进入选择角色界面",
            self._is_character_screen,
            profile="screen",
        ):
            raise NavigationError("点击重新登录后未进入选择角色界面")

    def _reach_server_screen(self) -> None:
        if self._is_server_screen():
            return
        if self._is_in_game():
            self._open_exit_panel_and_relogin()
        if not self._is_character_screen():
            raise NavigationError("当前既不是游戏、选择角色，也不是选择服务器界面")
        exit_button = self._find(Ui.CHARACTER_EXIT)
        if exit_button is None:
            exit_button = self.wait_for_step(
                "查找选择角色界面的退出登录按钮",
                lambda: self._find(Ui.CHARACTER_EXIT),
                profile="recognition",
            )
        if exit_button is None:
            raise NavigationError("连续 3 次未找到选择角色界面的退出登录按钮")
        self._click(exit_button)
        if not self.wait_for_step(
            "退出角色界面后进入服务器列表",
            self._is_server_screen,
            profile="screen",
        ):
            raise NavigationError("退出登录后未进入选择服务器界面")

    def _select_server(self, target: TargetRegion) -> None:
        left, top, right, bottom = Ui.SERVER_REGION
        if target.select_x is not None and target.select_y is not None:
            point = (target.select_x, target.select_y)
            source = "总控配置"
        else:
            point = self.wait_for_step(
                f"通过 OCR 定位大区 {_printable(target.name or target.code)}",
                lambda: self.vision.find_text(target, Ui.SERVER_REGION),
                profile="recognition",
            )
            if point is None:
                raise NavigationError(
                    f"大区未配置坐标，OCR 也未找到目标大区"
                    f"（已连续检测 3 次）: {target.name or target.code}"
                )
            source = "OCR 定位"
        if not (left <= point[0] < right and top <= point[1] < bottom):
            raise NavigationError(
                f"大区选择坐标 ({point[0]},{point[1]}) 不在服务器列表安全区域内"
            )
        print(
            f"[Lineage] 选择大区 id={target.region_id} "
            f"target='{_printable(target.name or target.code)}' source={source} "
            f"coordinate=({point[0]},{point[1]})"
        )
        self._click(point)
        confirm = self.wait_for_step(
            f"选中大区 {_printable(target.name or target.code)}",
            lambda: self._find(Ui.SERVER_CONFIRM, Ui.SERVER_REGION),
            profile="panel",
        )
        if confirm is None:
            raise NavigationError("选中大区后未找到确认按钮")
        self._click(confirm)
        if not self.wait_for_step(
            "确认大区后进入选择角色界面",
            self._is_character_screen,
            profile="screen",
        ):
            raise NavigationError("确认大区后未进入选择角色界面")

    def _select_character_and_login(self) -> None:
        color = self.vision.pixel(Ui.CHARACTER_SELECTED_PIXEL)
        if color == (0, 0, 0):
            left, top, right, bottom = Ui.CHARACTER_PICK_REGION
            self._click(((left + right) // 2, (top + bottom) // 2))
            selected = self.wait_for_step(
                "选择登录角色",
                lambda: self.vision.pixel(Ui.CHARACTER_SELECTED_PIXEL) != (0, 0, 0),
                profile="panel",
            )
            if not selected:
                raise NavigationError("点击角色后角色仍未选中")
        login = self.wait_for_step(
            "等待角色登录按钮可用",
            lambda: self._find(Ui.CHARACTER_LOGIN, Ui.CHARACTER_ACTION_REGION),
            profile="recognition",
        )
        if login is None:
            raise NavigationError("选择角色界面未找到登录按钮")
        self._click(login)
        if not self.wait_for_step(
            "角色登录后进入游戏主界面",
            self._is_in_game,
            profile="screen",
            fixed_wait=5.0,
        ):
            raise NavigationError("角色登录后未进入游戏")

    def ensure_inventory_open(self, recognition_images: list[str]) -> None:
        if not recognition_images:
            raise NavigationError("订单明细缺少物品识别图片")
        if any(
            self.vision.find_image(image, Ui.INVENTORY_REGION, threshold=0.90)
            for image in recognition_images
        ):
            return
        inventory = self._find(Ui.INVENTORY_BUTTON, Ui.INVENTORY_REGION)
        if inventory is None:
            inventory = self.wait_for_step(
                "查找物品栏按钮",
                lambda: self._find(Ui.INVENTORY_BUTTON, Ui.INVENTORY_REGION),
                profile="recognition",
            )
        if inventory is None:
            raise NavigationError("连续 3 次未找到物品栏按钮，无法打开物品栏")
        self._click(inventory)
        found = self.wait_for_step(
            "打开物品栏并识别订单物品",
            lambda: any(
                self.vision.find_image(image, Ui.INVENTORY_REGION, threshold=0.90)
                for image in recognition_images
            ),
            profile="recognition",
        )
        if not found:
            raise NavigationError("点击物品栏按钮后未识别到订单物品")

    def ensure_target_region(self, order: dict) -> TargetRegion:
        target = TargetRegion.from_order(order)
        self.window.focus()

        def client_ready() -> bool:
            self.window.validate_size()
            return True

        if not self.wait_for_step(
            "激活并确认游戏客户区可操作",
            client_ready,
            profile="screen",
            fixed_wait=1.0,
        ):
            raise NavigationError("激活游戏窗口后连续 3 次仍无法确认客户区可操作")

        print(
            "[Lineage] 每次交易重新选择订单大区: "
            f"{_printable(target.name or target.code)}，页码={target.select_page}"
        )
        self._reach_server_screen()
        self._select_server(target)
        self._select_character_and_login()

        recognition_images = list(dict.fromkeys(
            image
            for detail in (order.get("details") or [])
            for image in item_recognition_images(detail)
        ))
        self.ensure_inventory_open(recognition_images)
        if self.runtime_status is not None:
            self.runtime_status.update(
                game_id=order.get("game_id"),
                game_account_id=order.get("game_account_id"),
                region_id=target.region_id,
                client_status="logged_in",
                ui_health="ready",
            )
        return target


def build_navigator(
    hardware,
    runtime_status=None,
    account: str = "",
    cancelled: Optional[Callable[[], bool]] = None,
    input_controller: Optional[HumanizedInputController] = None,
) -> LineageSessionNavigator:
    window = ClientWindow.find(account=account)
    return LineageSessionNavigator(
        hardware=hardware,
        window=window,
        vision=TemplateVision(window),
        runtime_status=runtime_status,
        cancelled=cancelled,
        input_controller=input_controller,
    )
