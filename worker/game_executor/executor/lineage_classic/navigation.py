"""Lineage Classic 800x600 客户端的登录、切区与物品栏前置检查。"""

from __future__ import annotations

import base64
import binascii
import math
import os
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


class Ui:
    INVENTORY_REGION = (600, 10, 762, 330)
    CHARACTER_PICK_REGION = (136, 57, 225, 294)
    CHARACTER_ACTION_REGION = (17, 340, 464, 414)
    CHARACTER_SELECTED_PIXEL = (166, 311)
    SYSTEM_REGION = (600, 10, 783, 234)
    SERVER_REGION = (220, 107, 560, 430)
    CURRENT_REGION_NAME = (64, 450, 133, 468)
    FULL_CLIENT = (0, 0, 800, 600)

    INVENTORY_BUTTON = "物品栏按钮.png"
    IN_GAME = "已进入游戏.png"
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
    sort_order: int = 0

    @classmethod
    def from_order(cls, order: dict) -> "TargetRegion":
        try:
            raw_x = order.get("region_select_x")
            raw_y = order.get("region_select_y")
            if (raw_x is None) != (raw_y is None):
                raise NavigationError("后台订单的大区选择坐标 X、Y 必须同时提供")
            target = cls(
                region_id=int(order["region_id"]),
                name=str(order.get("region_name") or "").strip(),
                code=str(order.get("region_code") or "").strip(),
                select_x=int(raw_x) if raw_x is not None else None,
                select_y=int(raw_y) if raw_y is not None else None,
                sort_order=int(order.get("region_sort_order") or 0),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise NavigationError("后台订单缺少有效的大区定位信息") from exc
        if target.region_id <= 0:
            raise NavigationError("后台订单的大区 ID 无效")
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

    def focus(self) -> None:
        if win32gui.IsIconic(self.hwnd):
            win32gui.ShowWindow(self.hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(self.hwnd)
        time.sleep(0.3)

    def client_origin(self) -> tuple[int, int]:
        return win32gui.ClientToScreen(self.hwnd, (0, 0))

    def validate_size(self) -> None:
        left, top, right, bottom = win32gui.GetClientRect(self.hwnd)
        size = (right - left, bottom - top)
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
    ):
        self.hardware = hardware
        self.window = window
        self.vision = vision
        self.runtime_status = runtime_status
        self.sleep = sleep
        self.cancelled = cancelled or (lambda: False)
        self._known_region_id: Optional[int] = None

    def _click(self, point: tuple[int, int]) -> None:
        self._raise_if_cancelled()
        ox, oy = self.window.client_origin()
        x, y = point
        try:
            moved = self.hardware.mouse_move(ox + x, oy + y, jitter_x=0, jitter_y=0)
        except TypeError:
            moved = self.hardware.mouse_move(ox + x, oy + y)
        if moved is False or self.hardware.mouse_click() is False:
            raise NavigationError(f"硬件点击失败: ({x}, {y})")

    def click(self, point: tuple[int, int]) -> None:
        """按游戏客户区相对坐标点击，供交易执行器复用。"""
        self._click(point)

    def drag(self, start: tuple[int, int], end: tuple[int, int]) -> None:
        """按游戏客户区相对坐标拖拽。"""
        self._raise_if_cancelled()
        ox, oy = self.window.client_origin()
        if self.hardware.mouse_drag(
            ox + start[0], oy + start[1], ox + end[0], oy + end[1]
        ) is False:
            raise NavigationError(f"硬件拖拽失败: {start} -> {end}")

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

    def _is_in_game(self) -> bool:
        if self._find(Ui.IN_GAME, Ui.CURRENT_REGION_NAME, threshold=0.72) is not None:
            return True
        if self._find(Ui.INVENTORY_BUTTON, Ui.INVENTORY_REGION) is not None:
            return True
        return False

    def _is_character_screen(self) -> bool:
        return self._find(Ui.CHARACTER_SCREEN) is not None

    def _is_server_screen(self) -> bool:
        return self._find(Ui.SERVER_SCREEN, Ui.SERVER_REGION) is not None

    def _current_region_matches(self, target: TargetRegion) -> bool:
        if self._known_region_id == target.region_id:
            return True
        text = self.vision.read_text(Ui.CURRENT_REGION_NAME)
        if text:
            print(
                f"[Lineage] 当前大区 OCR='{_printable(text)}', "
                f"目标='{_printable(target.name or target.code)}'"
            )
        return region_text_matches(text, target)

    def _open_exit_panel_and_relogin(self) -> None:
        relogin = self._find(Ui.RELOGIN_BUTTON, Ui.SYSTEM_REGION)
        if relogin is None:
            trigger = self._find(Ui.EXIT_PANEL_TRIGGER, Ui.SYSTEM_REGION)
            if trigger is None:
                menu = self._find(Ui.MENU_BUTTON, Ui.SYSTEM_REGION)
                if menu is None:
                    raise NavigationError("未找到退出登录触发按钮或切换菜单按钮")
                self._click(menu)
                trigger = self._wait_for(
                    lambda: self._find(Ui.EXIT_PANEL_TRIGGER, Ui.SYSTEM_REGION),
                    timeout=5,
                )
            if trigger is None:
                raise NavigationError("打开切换菜单后仍未找到退出登录触发按钮")
            self._click(trigger)
            relogin = self._wait_for(
                lambda: self._find(Ui.RELOGIN_BUTTON, Ui.SYSTEM_REGION),
                timeout=5,
            )
        if relogin is None:
            raise NavigationError("未找到重新登录按钮")
        self._click(relogin)
        if not self._wait_for(self._is_character_screen, timeout=12):
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
            raise NavigationError("选择角色界面未找到退出登录按钮")
        self._click(exit_button)
        if not self._wait_for(self._is_server_screen, timeout=12):
            raise NavigationError("退出登录后未进入选择服务器界面")

    def _select_server(self, target: TargetRegion) -> None:
        left, top, right, bottom = Ui.SERVER_REGION
        if target.select_x is not None and target.select_y is not None:
            point = (target.select_x, target.select_y)
            source = "总控配置"
        else:
            point = self.vision.find_text(target, Ui.SERVER_REGION)
            if point is None:
                raise NavigationError(
                    f"大区未配置坐标，OCR 也未找到目标大区: {target.name or target.code}"
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
        confirm = self._wait_for(
            lambda: self._find(Ui.SERVER_CONFIRM, Ui.SERVER_REGION),
            timeout=5,
        )
        if confirm is None:
            raise NavigationError("选中大区后未找到确认按钮")
        self._click(confirm)
        if not self._wait_for(self._is_character_screen, timeout=15):
            raise NavigationError("确认大区后未进入选择角色界面")

    def _select_character_and_login(self) -> None:
        color = self.vision.pixel(Ui.CHARACTER_SELECTED_PIXEL)
        if color == (0, 0, 0):
            left, top, right, bottom = Ui.CHARACTER_PICK_REGION
            self._click(((left + right) // 2, (top + bottom) // 2))
            selected = self._wait_for(
                lambda: self.vision.pixel(Ui.CHARACTER_SELECTED_PIXEL) != (0, 0, 0),
                timeout=3,
            )
            if not selected:
                raise NavigationError("点击角色后角色仍未选中")
        login = self._wait_for(
            lambda: self._find(Ui.CHARACTER_LOGIN, Ui.CHARACTER_ACTION_REGION),
            timeout=5,
        )
        if login is None:
            raise NavigationError("选择角色界面未找到登录按钮")
        self._click(login)
        if not self._wait_for(self._is_in_game, timeout=30):
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
            raise NavigationError("未找到物品栏按钮，无法打开物品栏")
        self._click(inventory)
        found = self._wait_for(
            lambda: any(
                self.vision.find_image(image, Ui.INVENTORY_REGION, threshold=0.90)
                for image in recognition_images
            ),
            timeout=5,
        )
        if not found:
            raise NavigationError("点击物品栏按钮后未识别到订单物品")

    def ensure_target_region(self, order: dict) -> TargetRegion:
        target = TargetRegion.from_order(order)
        self.window.focus()
        self.window.validate_size()

        if self._is_in_game() and self._current_region_matches(target):
            print(f"[Lineage] 已在目标大区: {_printable(target.name or target.code)}")
        else:
            print(
                "[Lineage] 当前大区不匹配或无法确认，开始切换到: "
                f"{_printable(target.name or target.code)}"
            )
            self._reach_server_screen()
            self._select_server(target)
            self._select_character_and_login()
            current_text = self.vision.read_text(Ui.CURRENT_REGION_NAME)
            if current_text and not region_text_matches(current_text, target):
                raise NavigationError(
                    f"切区后 OCR 复核失败: current='{current_text}', target='{target.name or target.code}'"
                )
            self._known_region_id = target.region_id

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
) -> LineageSessionNavigator:
    window = ClientWindow.find(account=account)
    return LineageSessionNavigator(
        hardware=hardware,
        window=window,
        vision=TemplateVision(window),
        runtime_status=runtime_status,
        cancelled=cancelled,
    )
