"""Lineage Classic 800x600 客户端的登录、切区与物品栏前置检查。"""

from __future__ import annotations

import base64
import binascii
import math
import os
import random
import re
import sys
import threading
import time
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Callable, Optional, Protocol
from urllib.error import URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from common.config import BACKEND_WS_URL

from game_executor import storage as game_storage
from game_executor.executor.hardware.humanized import HumanizedInputController
from game_executor.executor.lineage_classic.paddle_ocr import (
    recognize_korean,
    recognize_korean_boxes,
)
from game_executor.executor.lineage_classic.player_name_ocr import (
    recognize_expected_player_name,
)

try:
    import cv2
    import numpy as np
    from PIL import Image, ImageDraw, ImageGrab
except ImportError:  # 单元测试和未安装 Trader 图像依赖的环境
    cv2 = None
    np = None
    Image = None
    ImageDraw = None
    ImageGrab = None

try:
    import win32api
    import win32con
    import win32gui
    import win32process
except ImportError:
    win32api = None
    win32con = None
    win32gui = None
    win32process = None


# 游戏分辨率与客户区均为 800x600，客户区左上角就是游戏坐标 (0, 0)。
# 标题栏位于客户区上方；若投影到游戏坐标系中，其 Y 为负数，不能把标题栏
# 或截图外沿当成固定的正坐标偏移。所有 Ui 坐标均相对客户区，运行时只通过
# ClientToScreen 动态换算屏幕绝对坐标。
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

STEP_VERIFY_ATTEMPTS = 30
CAPTURE_TIMEOUT_SECONDS = min(
    30.0,
    max(1.0, float(os.getenv("LINEAGE_CAPTURE_TIMEOUT_SECONDS", "5"))),
)
GAME_IMAGE_BASE_URL = os.getenv("GAME_IMAGE_BASE_URL", "").strip()
ACTION_DEBUG_IMAGES_ENABLED = False
ACTION_DEBUG_IMAGE_DIR = Path.cwd() / "lineage_action_debug"


@dataclass(frozen=True)
class StepWaitProfile:
    label: str
    fixed_wait: float
    random_min: float
    random_max: float
    probe_interval: float


STEP_WAIT_PROFILES = {
    # 除选服加载外，每个动作均直接在 0.5～1.5 秒内均匀随机首次等待。
    "screen": StepWaitProfile("画面切换", 0.0, 0.5, 1.5, 0.5),
    "panel": StepWaitProfile("面板操作", 0.0, 0.5, 1.5, 0.4),
    "recognition": StepWaitProfile("图像识别", 0.0, 0.5, 1.5, 0.3),
    # 点击目标大区后服务器需要加载，保留 2～5 秒的长等待例外。
    "server_connect": StepWaitProfile("服务器连接", 1.0, 1.0, 4.0, 1.0),
    "item_drag": StepWaitProfile("物品拖拽", 0.0, 0.5, 1.5, 0.3),
    "input": StepWaitProfile("数量输入", 0.0, 0.5, 1.5, 0.3),
    "final_verify": StepWaitProfile("结果验证", 0.0, 0.5, 1.5, 0.4),
}


class Ui:
    # 800x600 客户区右上物品格，以及底部快捷栏中的物品栏开关。
    INVENTORY_CONTENT_REGION = (600, 15, 770, 360)
    # 使用物品栏独有的右侧滚动条下箭头与底部边框判断打开状态；
    # 不使用可能被其他右侧面板复用的 Close 标识。
    INVENTORY_OPEN_REGION = (755, 290, 800, 370)
    # 切换菜单后快捷栏会横向变化，按钮可能位于 x=644 或 x=693。
    INVENTORY_BUTTON_REGION = (630, 560, 730, 600)
    INVENTORY_BUTTON_FALLBACK = (704, 585)
    # 兼容仍引用旧名称的扩展代码；新代码应明确使用 CONTENT/BUTTON 区域。
    INVENTORY_REGION = INVENTORY_CONTENT_REGION
    CHARACTER_PICK_REGION = (136, 57, 225, 294)
    # 角色界面右下角固定的 OK / Cancel 操作区。
    CHARACTER_ACTION_REGION = (640, 480, 780, 555)
    # 角色名称值的输入框内部，不包含边框、人物或动态选中特效。
    CHARACTER_NAME_VALUE_REGION = (212, 367, 450, 383)
    CHARACTER_VALUE_BRIGHTNESS = 70
    CHARACTER_VALUE_MIN_BRIGHT_PIXELS = 20
    SYSTEM_REGION = (600, 10, 783, 234)
    MENU_BUTTON_REGION = (785, 565, 800, 600)
    # 实机确认的切换按钮完整可点击范围（右、下边界按 Python 区域惯例不包含）。
    MENU_BUTTON_CLICK_REGION = (788, 570, 800, 600)
    EXIT_PANEL_TRIGGER_REGION = (755, 560, 795, 600)
    # 800x600 客户区底部 HP 状态条；实机模板左上角约为 (217,474)。
    IN_GAME_ANCHOR_REGION = (200, 465, 300, 500)
    SERVER_REGION = (220, 107, 560, 430)
    SERVER_SELECT_RADIUS_X = 20
    SERVER_SELECT_RADIUS_Y = 2
    SERVER_PAGINATION_REGION = (180, 350, 620, 500)
    ACCOUNT_CONFIRM_REGION = (580, 420, 700, 480)
    SERVER_PAGE_FIRST_CENTER = (340, 353)
    SERVER_PAGE_SPACING_X = 24
    SERVER_VISIBLE_PAGE_COUNT = 6
    FULL_CLIENT = (0, 0, 800, 600)

    INVENTORY_BUTTON = "物品栏按钮.png"
    INVENTORY_OPEN = "物品栏已打开.png"
    IN_GAME_ANCHOR = "已进入游戏.png"
    MENU_BUTTON = "切换菜单按钮.png"
    EXIT_PANEL_TRIGGER = "退出登录界面触发按钮.png"
    RELOGIN_BUTTON = "重新登录按钮.png"
    CHARACTER_SCREEN = "选人界面判断.png"
    CHARACTER_EXIT = "选人界面退出登录按钮.png"
    CHARACTER_LOGIN = "选人界面登录按钮.png"
    SERVER_SCREEN = "选择服务器界面判断.png"
    ACCOUNT_CONFIRM_BUTTON = "选中大区后的确认按钮.png"
    SERVER_CONFIRM = ACCOUNT_CONFIRM_BUTTON


class NavigationError(RuntimeError):
    pass


class NavigationCancelled(NavigationError):
    pass


class InventoryStateError(NavigationError):
    """物品栏面板未能切换到可可靠识别的状态。"""


class InventoryItemNotFoundError(NavigationError):
    """物品栏已就绪，但订单物品图像仍未识别到。"""


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


def _session_identifier(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip().casefold()


@dataclass(frozen=True)
class RegionSessionKey:
    game_id: str
    game_account_id: str
    window_account: str
    region_id: int

    @classmethod
    def from_order(
        cls,
        order: dict,
        target: TargetRegion,
        window_account: object = "",
    ) -> "RegionSessionKey":
        return cls(
            game_id=_session_identifier(order.get("game_id")),
            game_account_id=_session_identifier(order.get("game_account_id")),
            window_account=_session_identifier(window_account),
            region_id=target.region_id,
        )


class RegionSessionCache:
    """记录本进程已成功登录的游戏账号与大区。"""

    def __init__(self):
        self._lock = threading.Lock()
        self._key: Optional[RegionSessionKey] = None

    def snapshot(self) -> Optional[RegionSessionKey]:
        with self._lock:
            return self._key

    def matches(self, key: RegionSessionKey) -> bool:
        with self._lock:
            return self._key == key

    def remember(self, key: RegionSessionKey) -> None:
        with self._lock:
            self._key = key

    def invalidate(self) -> Optional[RegionSessionKey]:
        with self._lock:
            previous = self._key
            self._key = None
            return previous


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

    def _foreground_window(self) -> Optional[int]:
        get_foreground = getattr(win32gui, "GetForegroundWindow", None)
        if not callable(get_foreground):
            return None
        try:
            return int(get_foreground())
        except Exception:
            return None

    def _activate_normally(self) -> None:
        bring_to_top = getattr(win32gui, "BringWindowToTop", None)
        if callable(bring_to_top):
            try:
                bring_to_top(self.hwnd)
            except Exception:
                pass
        win32gui.SetForegroundWindow(self.hwnd)

    def _activate_with_attached_input(self) -> None:
        """临时共享前台线程输入队列，绕过 Windows 的普通前台切换限制。"""
        if win32api is None or win32process is None:
            raise RuntimeError("pywin32 前台线程接口不可用")

        current_thread = int(win32api.GetCurrentThreadId())
        foreground_hwnd = self._foreground_window()
        target_thread, _ = win32process.GetWindowThreadProcessId(self.hwnd)
        foreground_thread = 0
        if foreground_hwnd:
            foreground_thread, _ = win32process.GetWindowThreadProcessId(foreground_hwnd)

        attached_threads: list[int] = []
        try:
            for thread_id in (foreground_thread, target_thread):
                thread_id = int(thread_id or 0)
                if (
                    thread_id
                    and thread_id != current_thread
                    and thread_id not in attached_threads
                ):
                    win32process.AttachThreadInput(current_thread, thread_id, True)
                    attached_threads.append(thread_id)
            bring_to_top = getattr(win32gui, "BringWindowToTop", None)
            if callable(bring_to_top):
                try:
                    bring_to_top(self.hwnd)
                except Exception:
                    pass
            set_active = getattr(win32gui, "SetActiveWindow", None)
            if callable(set_active):
                try:
                    set_active(self.hwnd)
                except Exception:
                    pass
            win32gui.SetForegroundWindow(self.hwnd)
        finally:
            for thread_id in reversed(attached_threads):
                try:
                    win32process.AttachThreadInput(current_thread, thread_id, False)
                except Exception:
                    pass

    def _activate_with_topmost_pulse(self) -> None:
        """短暂提升窗口层级后立即还原，避免永久改变游戏窗口置顶状态。"""
        set_window_pos = getattr(win32gui, "SetWindowPos", None)
        if not callable(set_window_pos):
            raise RuntimeError("SetWindowPos 不可用")
        flags = (
            getattr(win32con, "SWP_NOMOVE", 0x0002)
            | getattr(win32con, "SWP_NOSIZE", 0x0001)
            | getattr(win32con, "SWP_SHOWWINDOW", 0x0040)
        )
        hwnd_topmost = getattr(win32con, "HWND_TOPMOST", -1)
        hwnd_notopmost = getattr(win32con, "HWND_NOTOPMOST", -2)
        try:
            set_window_pos(self.hwnd, hwnd_topmost, 0, 0, 0, 0, flags)
            win32gui.SetForegroundWindow(self.hwnd)
        finally:
            set_window_pos(self.hwnd, hwnd_notopmost, 0, 0, 0, 0, flags)

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

    def focus(self, timeout: float = 2.0) -> None:
        size = self.restore()
        if size == (0, 0):
            raise NavigationError("游戏窗口仍处于最小化状态，自动恢复后客户区暂时为 0x0")

        if self._foreground_window() == self.hwnd:
            return

        attempts: tuple[tuple[str, Callable[[], object]], ...] = (
            ("普通激活", self._activate_normally),
            ("附加前台线程", self._activate_with_attached_input),
            ("临时置顶激活", self._activate_with_topmost_pulse),
        )
        deadline = time.monotonic() + max(0.2, timeout)
        errors: list[str] = []
        while True:
            for name, activate in attempts:
                try:
                    activate()
                except Exception as exc:
                    errors.append(f"{name}: {exc}")
                if self._foreground_window() == self.hwnd:
                    time.sleep(0.3)
                    return
            if time.monotonic() >= deadline:
                break
            time.sleep(0.1)

        detail = "；".join(errors[-3:]) if errors else "Windows 未将目标窗口设为前台"
        raise NavigationError(
            "游戏窗口已恢复，但 Windows 拒绝切换到前台。"
            "请确认游戏执行器与游戏使用相同的管理员权限，"
            "并确认主机未锁屏、未切换用户且远程桌面会话仍处于活动状态。"
            f"最后尝试：{detail}"
        )

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
    def bright_pixel_count(self, region: tuple[int, int, int, int], threshold: int) -> int: ...
    def read_text(self, region: tuple[int, int, int, int]) -> str: ...
    def find_text(self, target: TargetRegion, region: tuple[int, int, int, int]) -> Optional[tuple[int, int]]: ...
    def find_page_number(self, page: int, region: tuple[int, int, int, int]) -> Optional[tuple[int, int]]: ...
    def find_image(self, image_source: str, region: tuple[int, int, int, int], threshold: float = 0.90) -> Optional[tuple[int, int]]: ...


@dataclass(frozen=True)
class OcrResult:
    text: str
    confidence: float
    verified: bool = False


class TemplateVision:
    def __init__(self, window: ClientWindow, image_dir: Optional[Path] = None):
        if cv2 is None or ImageGrab is None:
            raise NavigationError("未安装 opencv-python/Pillow，无法识别游戏界面")
        self.window = window
        self.image_dir = image_dir or Path(__file__).with_name("images")
        self._templates: dict[str, object] = {}
        self._dynamic_templates: dict[str, object] = {}
        self._ocr_warning_printed = False
        self._recent_match_visuals: list[dict[str, object]] = []
        self._debug_image_sequence = 0

    def _capture(self, region: tuple[int, int, int, int]):
        ox, oy = self.window.client_origin()
        left, top, right, bottom = region
        bbox = (ox + left, oy + top, ox + right, oy + bottom)
        completed = threading.Event()
        result: dict[str, object] = {}

        def grab() -> None:
            try:
                result["image"] = ImageGrab.grab(bbox=bbox, all_screens=True)
            except BaseException as exc:
                result["error"] = exc
            finally:
                completed.set()

        started = time.monotonic()
        threading.Thread(
            target=grab,
            name="lineage-screen-capture",
            daemon=True,
        ).start()
        if not completed.wait(CAPTURE_TIMEOUT_SECONDS):
            raise NavigationError(
                f"游戏画面截图超过 {CAPTURE_TIMEOUT_SECONDS:g} 秒未返回，"
                f"截图区域={region}；请检查桌面会话、窗口遮挡和运行权限"
            )
        error = result.get("error")
        if error is not None:
            raise NavigationError(f"游戏画面截图失败，截图区域={region}: {error}")
        elapsed = time.monotonic() - started
        if elapsed >= 1.0:
            print(
                f"[Lineage][截图] 截图完成但耗时较长: {elapsed:.2f}s，区域={region}",
                flush=True,
            )
        image = result["image"]
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
        point, _confidence = self._match_template_result(
            source,
            needle,
            region,
            threshold,
        )
        return point

    def find_with_confidence(
        self,
        template: str,
        region: tuple[int, int, int, int],
        threshold: float = 0.84,
    ) -> tuple[Optional[tuple[int, int]], float]:
        """返回识别坐标及最高匹配度，供关键流程输出可人工复核的判断日志。"""
        source = self._capture(region)
        needle = self._template(template)
        point, confidence = self._match_template_result(
            source,
            needle,
            region,
            threshold,
        )
        if point is not None:
            height, width = needle.shape[:2]
            left = point[0] - width // 2
            top = point[1] - height // 2
            self._recent_match_visuals.append({
                "template": template,
                "point": point,
                "search_region": region,
                "matched_region": (
                    left,
                    top,
                    left + width - 1,
                    top + height - 1,
                ),
                "confidence": confidence,
                "threshold": threshold,
            })
            self._recent_match_visuals = self._recent_match_visuals[-12:]
        return point, confidence

    def template_size(self, template: str) -> tuple[int, int]:
        """返回模板的像素宽高，用于输出实际命中的客户区范围。"""
        height, width = self._template(template).shape[:2]
        return int(width), int(height)

    def save_action_visualization(self, action: dict[str, object]) -> Optional[str]:
        """保存点击、拖拽或键盘动作的 800x600 客户区示意图。"""
        if not ACTION_DEBUG_IMAGES_ENABLED:
            return None
        if Image is None or ImageDraw is None:
            raise NavigationError("未安装 Pillow，无法生成操作标注图")
        action_name = str(action.get("action") or "")
        if action_name not in {
            "mouse_click",
            "mouse_drag",
            "key_type",
            "key_press",
            "key_combo",
        }:
            return None

        source = self._capture(Ui.FULL_CLIENT)
        image = Image.fromarray(source[:, :, ::-1]).convert("RGB")
        draw = ImageDraw.Draw(image)

        if action_name == "mouse_click":
            drawn = self._draw_click_action_visualization(draw, action)
        elif action_name == "mouse_drag":
            drawn = self._draw_drag_action_visualization(draw, action)
        else:
            drawn = self._draw_keyboard_action_visualization(draw, action)
        if not drawn:
            return None

        ACTION_DEBUG_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
        self._debug_image_sequence += 1
        now = time.time()
        timestamp = time.strftime("%Y%m%d_%H%M%S", time.localtime(now))
        milliseconds = int((now % 1) * 1000)
        path = ACTION_DEBUG_IMAGE_DIR / (
            f"lineage_action_{timestamp}_{milliseconds:03d}_"
            f"{self._debug_image_sequence:04d}.png"
        )
        image.save(path, format="PNG")
        return str(path.resolve())

    def _draw_click_action_visualization(
        self,
        draw,
        action: dict[str, object],
    ) -> bool:
        target = action.get("client_target")
        actual = action.get("client_actual")
        action_bounds = action.get("client_action_bounds")
        if not (
            isinstance(target, list)
            and len(target) == 2
            and isinstance(actual, list)
            and len(actual) == 2
            and isinstance(action_bounds, list)
            and len(action_bounds) == 4
        ):
            return False

        nearest_match = None
        nearest_distance = float("inf")
        for match in self._recent_match_visuals:
            point = match.get("point")
            if not isinstance(point, tuple) or len(point) != 2:
                continue
            distance = math.hypot(point[0] - target[0], point[1] - target[1])
            if distance < nearest_distance:
                nearest_distance = distance
                nearest_match = match
        if nearest_distance > 5:
            nearest_match = None

        if nearest_match is not None:
            search_region = nearest_match["search_region"]
            matched_region = nearest_match["matched_region"]
            search_left, search_top, search_right, search_bottom = search_region
            draw.rectangle(
                (
                    search_left,
                    search_top,
                    search_right - 1,
                    search_bottom - 1,
                ),
                outline=(255, 165, 0),
                width=2,
            )
            draw.rectangle(
                tuple(matched_region),
                outline=(0, 220, 255),
                width=2,
            )

        draw.rectangle(
            tuple(action_bounds),
            outline=(0, 255, 0),
            width=3,
        )
        self._draw_debug_point(draw, tuple(target), (0, 128, 255), radius=6)
        self._draw_debug_point(draw, tuple(actual), (255, 0, 0), radius=4)

        legend_lines = [
            "ORANGE: search region",
            "CYAN: matched template",
            (
                "GREEN: action region "
                f"X[{action_bounds[0]},{action_bounds[2]}] "
                f"Y[{action_bounds[1]},{action_bounds[3]}]"
            ),
            f"BLUE: target ({target[0]},{target[1]})",
            f"RED: actual ({actual[0]},{actual[1]})",
        ]
        draw.rectangle((4, 4, 370, 86), fill=(0, 0, 0))
        for index, line in enumerate(legend_lines):
            draw.text((10, 8 + index * 15), line, fill=(255, 255, 255))
        return True

    def _draw_drag_action_visualization(
        self,
        draw,
        action: dict[str, object],
    ) -> bool:
        target_start = action.get("client_target_start")
        target_end = action.get("client_target_end")
        actual_start = action.get("client_actual_start")
        actual_end = action.get("client_actual_end")
        points = (target_start, target_end, actual_start, actual_end)
        if not all(isinstance(point, list) and len(point) == 2 for point in points):
            return False

        start_bounds = action.get("client_start_action_bounds")
        end_bounds = action.get("client_end_action_bounds")
        for bounds in (start_bounds, end_bounds):
            if isinstance(bounds, list) and len(bounds) == 4:
                draw.rectangle(tuple(bounds), outline=(0, 255, 0), width=3)

        target_start_point = tuple(int(value) for value in target_start)
        target_end_point = tuple(int(value) for value in target_end)
        actual_start_point = tuple(int(value) for value in actual_start)
        actual_end_point = tuple(int(value) for value in actual_end)
        self._draw_debug_point(
            draw,
            target_start_point,
            (0, 128, 255),
            radius=6,
        )
        self._draw_debug_point(
            draw,
            target_end_point,
            (0, 128, 255),
            radius=6,
        )

        trajectory = self._debug_drag_trajectory(
            actual_start_point,
            actual_end_point,
        )
        draw.line(trajectory, fill=(255, 0, 255), width=4)
        if len(trajectory) >= 2:
            self._draw_debug_arrow_head(
                draw,
                trajectory[-2],
                trajectory[-1],
                (255, 0, 255),
            )
        self._draw_debug_point(
            draw,
            actual_start_point,
            (255, 0, 0),
            radius=4,
        )
        self._draw_debug_point(
            draw,
            actual_end_point,
            (255, 0, 0),
            radius=4,
        )
        draw.text(
            (actual_start_point[0] + 8, actual_start_point[1] - 14),
            "START",
            fill=(255, 255, 255),
            stroke_width=2,
            stroke_fill=(0, 0, 0),
        )
        draw.text(
            (actual_end_point[0] + 8, actual_end_point[1] - 14),
            "END",
            fill=(255, 255, 255),
            stroke_width=2,
            stroke_fill=(0, 0, 0),
        )

        legend_lines = [
            "DRAG TRAJECTORY",
            "GREEN: allowed start/end regions",
            (
                "BLUE: configured targets "
                f"({target_start_point[0]},{target_start_point[1]}) -> "
                f"({target_end_point[0]},{target_end_point[1]})"
            ),
            (
                "RED: actual endpoints "
                f"({actual_start_point[0]},{actual_start_point[1]}) -> "
                f"({actual_end_point[0]},{actual_end_point[1]})"
            ),
            "MAGENTA: drag direction and trajectory",
        ]
        draw.rectangle((4, 4, 492, 86), fill=(0, 0, 0))
        for index, line in enumerate(legend_lines):
            draw.text((10, 8 + index * 15), line, fill=(255, 255, 255))
        return True

    @staticmethod
    def _debug_drag_trajectory(
        start: tuple[int, int],
        end: tuple[int, int],
    ) -> list[tuple[int, int]]:
        """生成仅用于标注图的稳定曲线；硬件仍负责真正的拟人化轨迹。"""
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        distance = math.hypot(dx, dy)
        if distance < 1:
            return [start, end]
        bend = min(42.0, max(12.0, distance * 0.10))
        control = (
            (start[0] + end[0]) / 2 - dy / distance * bend,
            (start[1] + end[1]) / 2 + dx / distance * bend,
        )
        result = []
        for index in range(25):
            t = index / 24
            one_minus_t = 1 - t
            result.append((
                round(
                    one_minus_t * one_minus_t * start[0]
                    + 2 * one_minus_t * t * control[0]
                    + t * t * end[0]
                ),
                round(
                    one_minus_t * one_minus_t * start[1]
                    + 2 * one_minus_t * t * control[1]
                    + t * t * end[1]
                ),
            ))
        return result

    @staticmethod
    def _draw_debug_arrow_head(
        draw,
        before: tuple[int, int],
        tip: tuple[int, int],
        color: tuple[int, int, int],
    ) -> None:
        angle = math.atan2(tip[1] - before[1], tip[0] - before[0])
        length = 13
        spread = math.pi / 6
        left = (
            tip[0] - length * math.cos(angle - spread),
            tip[1] - length * math.sin(angle - spread),
        )
        right = (
            tip[0] - length * math.cos(angle + spread),
            tip[1] - length * math.sin(angle + spread),
        )
        draw.polygon(
            [tip, (round(left[0]), round(left[1])), (round(right[0]), round(right[1]))],
            fill=color,
        )

    @classmethod
    def _draw_keyboard_action_visualization(
        cls,
        draw,
        action: dict[str, object],
    ) -> bool:
        action_name = str(action.get("action") or "")
        if action_name == "key_type":
            text = str(action.get("text") or "")
            plan = action.get("typing_plan")
            keys = [
                str(item.get("key") or "")
                for item in plan
                if isinstance(item, dict)
            ] if isinstance(plan, list) else list(text)
            title = "KEYBOARD INPUT"
            summary = f"Text: {cls._ascii_debug_text(text)}"
            timing = "Each key uses the logged randomized hold and gap timing"
        elif action_name == "key_press":
            keys = [str(action.get("key") or "")]
            title = "KEY PRESS"
            summary = f"Key: {cls._ascii_debug_text(keys[0])}"
            timing = f"Hold: {int(action.get('hold_ms') or 0)} ms"
        elif action_name == "key_combo":
            raw_keys = action.get("keys")
            keys = [str(key) for key in raw_keys] if isinstance(raw_keys, list) else []
            title = "KEY COMBINATION"
            summary = "Keys: " + "+".join(cls._ascii_debug_text(key) for key in keys)
            timing = f"Hold: {int(action.get('hold_ms') or 0)} ms"
        else:
            return False

        safe_keys = [cls._ascii_debug_text(key) for key in keys]
        panel_bottom = 136
        draw.rectangle((4, 4, 795, panel_bottom), fill=(0, 0, 0))
        draw.rectangle((4, 4, 795, panel_bottom), outline=(0, 220, 255), width=2)
        draw.text((14, 12), title, fill=(0, 220, 255))
        draw.text((14, 30), summary[:105], fill=(255, 255, 255))
        draw.text((14, 48), timing, fill=(180, 180, 180))

        x = 14
        y = 72
        visible_keys = safe_keys[:16]
        if len(safe_keys) > len(visible_keys):
            visible_keys.append("...")
        for index, key in enumerate(visible_keys):
            label = key or "SPACE"
            cap_width = max(42, min(92, 22 + len(label) * 8))
            if x + cap_width > 780:
                break
            draw.rectangle((x + 3, y + 4, x + cap_width + 3, y + 42), fill=(60, 60, 60))
            draw.rectangle(
                (x, y, x + cap_width, y + 38),
                fill=(235, 235, 235),
                outline=(120, 120, 120),
                width=2,
            )
            text_left = x + max(7, (cap_width - len(label) * 7) // 2)
            draw.text((text_left, y + 13), label, fill=(20, 20, 20))
            x += cap_width + 10
            if action_name == "key_combo" and index + 1 < len(visible_keys):
                draw.text((x - 6, y + 13), "+", fill=(255, 255, 255))
        return True

    @staticmethod
    def _ascii_debug_text(value: object) -> str:
        text = str(value)
        try:
            text.encode("ascii")
            return text
        except UnicodeEncodeError:
            return text.encode("unicode_escape").decode("ascii")

    @staticmethod
    def _draw_debug_point(draw, point, color, *, radius: int) -> None:
        x, y = (int(value) for value in point)
        draw.ellipse(
            (x - radius, y - radius, x + radius, y + radius),
            outline=color,
            width=2,
        )
        draw.line((x - radius - 2, y, x + radius + 2, y), fill=color, width=2)
        draw.line((x, y - radius - 2, x, y + radius + 2), fill=color, width=2)

    @staticmethod
    def _match_template(source, needle, region, threshold: float) -> Optional[tuple[int, int]]:
        point, _confidence = TemplateVision._match_template_result(
            source,
            needle,
            region,
            threshold,
        )
        return point

    @staticmethod
    def _match_template_result(
        source,
        needle,
        region,
        threshold: float,
    ) -> tuple[Optional[tuple[int, int]], float]:
        height, width = needle.shape[:2]
        if source.shape[0] < height or source.shape[1] < width:
            return None, -1.0
        result = cv2.matchTemplate(source, needle, cv2.TM_CCOEFF_NORMED)
        _, confidence, _, location = cv2.minMaxLoc(result)
        if confidence < threshold:
            return None, float(confidence)
        point = (
            region[0] + location[0] + width // 2,
            region[1] + location[1] + height // 2,
        )
        return point, float(confidence)

    @staticmethod
    def _absolute_image_url(image_source: str) -> str:
        parsed = urlparse(image_source)
        if parsed.scheme in {"http", "https"}:
            return image_source
        if GAME_IMAGE_BASE_URL:
            configured = urlparse(GAME_IMAGE_BASE_URL)
            if configured.scheme not in {"http", "https"} or not configured.netloc:
                raise NavigationError(
                    "GAME_IMAGE_BASE_URL 必须是可访问的 http:// 或 https:// 地址"
                )
            return urljoin(GAME_IMAGE_BASE_URL.rstrip("/") + "/", image_source)
        backend = urlparse(BACKEND_WS_URL)
        if backend.scheme not in {"ws", "wss"} or not backend.netloc:
            raise NavigationError(
                "BACKEND_WS_URL 格式不正确，无法推导游戏识别图片地址"
            )
        scheme = "https" if backend.scheme == "wss" else "http"
        return urljoin(f"{scheme}://{backend.netloc}/", image_source)

    def _dynamic_template(self, image_source: str):
        key = str(image_source or "").strip()
        if not key:
            raise NavigationError("订单物品缺少识别图片")
        if key in self._dynamic_templates:
            return self._dynamic_templates[key]
        started = time.monotonic()
        print(
            f"[Lineage][物品识别图] 开始加载: {_printable(key)}",
            flush=True,
        )
        resolved_url = ""
        try:
            if key.startswith("data:image/"):
                _header, payload = key.split(",", 1)
                raw = base64.b64decode(payload, validate=True)
            elif game_storage.is_enabled():
                raw, resolved_url = game_storage.read_image(key)
                print(
                    f"[Lineage][物品识别图] RustFS 对象地址: "
                    f"{_printable(resolved_url)}",
                    flush=True,
                )
            else:
                resolved_url = self._absolute_image_url(key)
                print(
                    f"[Lineage][物品识别图] 解析下载地址: "
                    f"{_printable(resolved_url)}",
                    flush=True,
                )
                request = Request(
                    resolved_url,
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
        except game_storage.StorageImageError as exc:
            raise NavigationError(str(exc)) from exc
        except (OSError, URLError, ValueError, binascii.Error) as exc:
            target = resolved_url or key
            raise NavigationError(
                f"加载物品识别图片失败: {key}（解析地址: {target}）"
            ) from exc
        if template is None:
            raise NavigationError(f"无法解码物品识别图片: {key}")
        self._dynamic_templates[key] = template
        height, width = template.shape[:2]
        print(
            f"[Lineage][物品识别图] 加载完成: {_printable(key)}，"
            f"size={width}x{height}，耗时={time.monotonic() - started:.2f}s",
            flush=True,
        )
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

    def bright_pixel_count(
        self,
        region: tuple[int, int, int, int],
        threshold: int,
    ) -> int:
        source = self._capture(region)
        grayscale = cv2.cvtColor(source, cv2.COLOR_BGR2GRAY)
        return int(np.count_nonzero(grayscale > int(threshold)))

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

    def read_player_name_result(
        self,
        region: tuple[int, int, int, int],
        expected_name: str,
    ) -> OcrResult:
        """按订单姓名将英文/韩文分段后分别识别。"""
        source = self._capture(region)
        try:
            result = recognize_expected_player_name(source, expected_name)
            run_details = "；".join(
                f"{run.kind} expected={run.expected!r} "
                f"observed={run.observed!r} "
                f"visual={run.visual_observed!r} "
                f"confidence={run.confidence:.1f} "
                f"high_risk_equivalent={run.high_risk_equivalent} "
                f"cell=X[{region[0] + run.left},{region[0] + run.right - 1}] "
                f"ocr=X[{region[0] + run.crop_left},"
                f"{region[0] + run.crop_right - 1}]"
                for run in result.runs
            )
            print(
                f"[Lineage][玩家名分段识别] expected={expected_name!r}，"
                f"observed={result.text!r}，"
                f"visual_observed={result.visual_observed!r}，"
                f"min_confidence={result.confidence:.1f}，"
                f"avg_confidence={result.average_confidence:.1f}，"
                f"verified={result.verified}，strategy={result.strategy}；"
                f"{run_details}",
                flush=True,
            )
            return OcrResult(
                result.text,
                result.confidence,
                verified=result.verified,
            )
        except Exception as exc:
            print(
                f"[Lineage][玩家名分段识别] 执行失败，转用整行韩文 OCR 并保留人工复核: "
                f"{exc}",
                flush=True,
            )
            scaled = cv2.resize(
                source, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC
            )
            enhanced = cv2.copyMakeBorder(
                scaled, 12, 12, 12, 12, cv2.BORDER_REPLICATE
            )
            try:
                text, confidence = recognize_korean(enhanced)
                return OcrResult(text, confidence)
            except Exception:
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

    def find_page_number(
        self,
        page: int,
        region: tuple[int, int, int, int],
    ) -> Optional[tuple[int, int]]:
        """通过 OCR 定位服务器列表底部的数字分页按钮。"""
        source = self._capture(region)
        scale = 4
        border = 12
        scaled = cv2.resize(source, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        enhanced = cv2.copyMakeBorder(
            scaled, border, border, border, border, cv2.BORDER_REPLICATE
        )
        expected = str(int(page))
        try:
            boxes = recognize_korean_boxes(enhanced)
        except Exception as exc:
            if not self._ocr_warning_printed:
                print(f"[Lineage] PaddleOCR 不可用，无法定位服务器分页按钮: {exc}")
                self._ocr_warning_printed = True
            return None
        for box in boxes:
            token = "".join(ch for ch in str(box.text).strip() if ch.isdigit())
            if box.confidence < OCR_MIN_CONFIDENCE or token != expected:
                continue
            center_x, center_y = box.center
            point = (
                region[0] + int((center_x - border) / scale + 0.5),
                region[1] + int((center_y - border) / scale + 0.5),
            )
            print(
                f"[Lineage] OCR 定位服务器页码 {expected}: "
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


def item_recognition_images(detail: dict) -> tuple[str, ...]:
    """返回可用的物品识别图；未选中/选中状态至少提供一张即可。"""
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
    images = tuple(dict.fromkeys(
        image for image in (unselected, selected) if image
    ))
    if not images:
        raise NavigationError(
            f"物品 {label} 缺少识别图片（未选中/选中状态至少提供一张）"
        )
    return images


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
        region_session_cache: Optional[RegionSessionCache] = None,
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
        self.region_session_cache = region_session_cache
        action_visualizer = getattr(self.vision, "save_action_visualization", None)
        set_action_visualizer = getattr(self.input, "set_action_visualizer", None)
        if callable(action_visualizer) and callable(set_action_visualizer):
            set_action_visualizer(action_visualizer)

    def _screen_bounds(self) -> tuple[int, int, int, int]:
        ox, oy = self.window.client_origin()
        return ox, oy, ox + CLIENT_SIZE[0] - 1, oy + CLIENT_SIZE[1] - 1

    def _click(
        self,
        point: tuple[int, int],
        *,
        radius_x: Optional[int] = None,
        radius_y: Optional[int] = None,
        client_bounds: Optional[tuple[int, int, int, int]] = None,
    ) -> None:
        self._raise_if_cancelled()
        ox, oy = self.window.client_origin()
        x, y = point
        if client_bounds is None:
            screen_bounds = self._screen_bounds()
        else:
            left, top, right, bottom = client_bounds
            screen_bounds = (ox + left, oy + top, ox + right, oy + bottom)
        if self.input.click_at(
            ox + x,
            oy + y,
            radius_x=radius_x,
            radius_y=radius_y,
            bounds=screen_bounds,
            coordinate_origin=(ox, oy),
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

    def move(
        self,
        point: tuple[int, int],
        *,
        radius_x: Optional[int] = None,
        radius_y: Optional[int] = None,
    ) -> None:
        """将鼠标移动到游戏客户区目标点，不执行点击。"""
        self._raise_if_cancelled()
        ox, oy = self.window.client_origin()
        x, y = point
        if self.input.move_to(
            ox + x,
            oy + y,
            radius_x=radius_x,
            radius_y=radius_y,
            bounds=self._screen_bounds(),
            coordinate_origin=(ox, oy),
        ) is False:
            self._raise_if_cancelled()
            raise NavigationError(f"硬件移动鼠标失败: ({x}, {y})")

    def _click_menu_button(self) -> None:
        """只在实机确认的切换按钮范围内变化落点。"""
        left, top, right, bottom = Ui.MENU_BUTTON_CLICK_REGION
        # 避开一像素边沿；传入精确边界，避免通用拟人化半径越出小按钮。
        safe_bounds = (left + 1, top + 1, right - 2, bottom - 2)
        safe_left, safe_top, safe_right, safe_bottom = safe_bounds
        center = (
            (safe_left + safe_right) // 2,
            (safe_top + safe_bottom) // 2,
        )
        print(
            "[Lineage][切换大区] 点击切换菜单按钮，"
            f"按钮范围=X[{left},{right - 1}] Y[{top},{bottom - 1}]，"
            f"安全随机范围=X[{safe_left},{safe_right}] "
            f"Y[{safe_top},{safe_bottom}]",
            flush=True,
        )
        self._click(
            center,
            radius_x=safe_right - safe_left,
            radius_y=safe_bottom - safe_top,
            client_bounds=safe_bounds,
        )

    def drag(self, start: tuple[int, int], end: tuple[int, int]) -> None:
        """按游戏客户区相对坐标执行起终点均有界变化的拖拽。"""
        self._raise_if_cancelled()
        ox, oy = self.window.client_origin()
        if self.input.drag(
            (ox + start[0], oy + start[1]),
            (ox + end[0], oy + end[1]),
            bounds=self._screen_bounds(),
            coordinate_origin=(ox, oy),
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

    def _find_for_decision(
        self,
        label: str,
        template: str,
        region=Ui.FULL_CLIENT,
        threshold: float = 0.84,
        log_category: str = "菜单判断",
    ) -> Optional[tuple[int, int]]:
        """输出关键按钮的原始识别结果，不只输出最终流程结论。"""
        detailed_find = getattr(self.vision, "find_with_confidence", None)
        if callable(detailed_find):
            point, confidence = detailed_find(template, region, threshold)
        else:
            point = self._find(template, region, threshold)
            confidence = None
        coordinate = (
            f"({point[0]},{point[1]})" if point is not None else "无"
        )
        matched_region = "无"
        if point is not None:
            template_size = getattr(self.vision, "template_size", None)
            if callable(template_size):
                width, height = template_size(template)
                left = point[0] - width // 2
                top = point[1] - height // 2
                right = left + width - 1
                bottom = top + height - 1
                matched_region = (
                    f"X[{left},{right}] Y[{top},{bottom}] "
                    f"size={width}x{height}"
                )
        confidence_text = (
            f"{confidence:.4f}" if confidence is not None else "当前识别器未提供"
        )
        search_left, search_top, search_right, search_bottom = region
        print(
            f"[Lineage][{log_category}] {label}: "
            f"结果={'命中' if point is not None else '未命中'}，"
            f"coordinate={coordinate}，confidence={confidence_text}，"
            f"threshold={threshold:.2f}，"
            f"matched_region={matched_region}，"
            f"search_region=X[{search_left},{search_right - 1}] "
            f"Y[{search_top},{search_bottom - 1}]，"
            f"template={template}",
            flush=True,
        )
        return point

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
        probe_interval: Optional[float] = None,
        retry_wait_range: Optional[tuple[float, float]] = None,
    ):
        """动作后先做人性化等待，再固定循环检测下一步状态 30 次。"""
        timing = STEP_WAIT_PROFILES.get(profile)
        if timing is None:
            raise ValueError(f"未知步骤等待类型: {profile}")
        fixed_seconds = max(0.0, float(timing.fixed_wait))
        random_min = timing.random_min
        random_max = timing.random_max
        random_seconds = float(self.random_uniform(
            random_min,
            random_max,
        ))
        random_seconds = min(
            random_max,
            max(random_min, random_seconds),
        )
        total_wait = fixed_seconds + random_seconds
        max_attempts = STEP_VERIFY_ATTEMPTS
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
                if retry_wait_range is None:
                    self._sleep_interruptibly(check_interval)
                else:
                    retry_min = max(0.0, float(retry_wait_range[0]))
                    retry_max = max(retry_min, float(retry_wait_range[1]))
                    retry_seconds = float(self.random_uniform(
                        retry_min,
                        retry_max,
                    ))
                    retry_seconds = min(
                        retry_max,
                        max(retry_min, retry_seconds),
                    )
                    print(
                        f"[Lineage][步骤重等] {step_name}: "
                        f"第 {attempt}/{max_attempts} 次未就绪，"
                        f"再次随机等待 {retry_seconds:.2f}s",
                        flush=True,
                    )
                    self._sleep_interruptibly(retry_seconds)

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
    ) -> None:
        """没有可靠视觉锚点的动作仍执行统一等待并记录一次完成检测。"""
        self.wait_for_step(
            step_name,
            lambda: True,
            profile=profile,
        )

    def _is_in_game(self) -> bool:
        # 该锚点位于游戏主界面的固定状态栏区域，不依赖物品栏或菜单是否展开。
        in_game_anchor = self._find(
            Ui.IN_GAME_ANCHOR,
            Ui.IN_GAME_ANCHOR_REGION,
            threshold=0.72,
        )
        if in_game_anchor is not None:
            print(
                "[Lineage][界面识别] 游戏主界面状态条已命中，"
                f"coordinate=({in_game_anchor[0]},{in_game_anchor[1]})，"
                "threshold=0.72",
                flush=True,
            )
            return True
        if self._find_menu_button() is not None:
            return True
        if self._find(
            Ui.EXIT_PANEL_TRIGGER,
            Ui.EXIT_PANEL_TRIGGER_REGION,
        ) is not None:
            return True
        # 找到任意一个主界面锚点即可返回，避免 eager tuple 无条件连续截图四次。
        for template, region in (
            (Ui.INVENTORY_BUTTON, Ui.INVENTORY_BUTTON_REGION),
            (Ui.RELOGIN_BUTTON, Ui.SYSTEM_REGION),
        ):
            if self._find(template, region) is not None:
                return True
        return False

    def _find_menu_button(self):
        # 右下角箭头在菜单开/关状态下仅有细微差异。搜索区域足够小，
        # 使用 0.60 可兼容实机关闭态约 0.63、打开态约 0.99 的匹配结果。
        return self._find(
            Ui.MENU_BUTTON,
            Ui.MENU_BUTTON_REGION,
            threshold=0.60,
        )

    def _is_character_screen(self) -> bool:
        return self._find(Ui.CHARACTER_SCREEN) is not None

    def _is_server_screen(self) -> bool:
        return self._find(Ui.SERVER_SCREEN, Ui.SERVER_REGION) is not None

    def _trace_screen_probe(
        self,
        label: str,
        predicate: Callable[[], object],
    ) -> bool:
        """记录同步截图/识别的边界，避免耗时识别期间看起来像无响应。"""
        self._raise_if_cancelled()
        started = time.monotonic()
        print(f"[Lineage][界面识别] 开始判断: {label}", flush=True)
        try:
            matched = bool(predicate())
        except Exception as exc:
            elapsed = time.monotonic() - started
            print(
                f"[Lineage][界面识别] 判断异常: {label}，"
                f"耗时={elapsed:.2f}s，原因={exc}",
                flush=True,
            )
            raise
        elapsed = time.monotonic() - started
        print(
            f"[Lineage][界面识别] 判断完成: {label}="
            f"{'是' if matched else '否'}，耗时={elapsed:.2f}s",
            flush=True,
        )
        return matched

    def _open_exit_panel_and_relogin(self) -> None:
        relogin = self._find_for_decision(
            "Restart 操作面板按钮",
            Ui.RELOGIN_BUTTON,
            Ui.SYSTEM_REGION,
        )
        if relogin is None:
            trigger = self._find_for_decision(
                "紫色 Restart 面板触发按钮",
                Ui.EXIT_PANEL_TRIGGER,
                Ui.EXIT_PANEL_TRIGGER_REGION,
            )
            menu = self._find_for_decision(
                "右下角切换菜单按钮",
                Ui.MENU_BUTTON,
                Ui.MENU_BUTTON_REGION,
                threshold=0.60,
            )
            if trigger is None:
                if menu is None:
                    menu = self.wait_for_step(
                        "查找切换菜单按钮",
                        lambda: self._find_for_decision(
                            "右下角切换菜单按钮（重试）",
                            Ui.MENU_BUTTON,
                            Ui.MENU_BUTTON_REGION,
                            threshold=0.60,
                        ),
                        profile="recognition",
                    )
                if menu is None:
                    print(
                        "[Lineage][菜单判断结论] 未识别到 Restart、紫色触发按钮"
                        "或右下角切换按钮，无法决定下一步",
                        flush=True,
                    )
                    raise NavigationError(
                        f"连续 {STEP_VERIFY_ATTEMPTS} 次未找到"
                        "退出登录触发按钮或切换菜单按钮"
                    )
                print(
                    "[Lineage][菜单判断结论] 未识别到紫色触发按钮，"
                    "但识别到右下角切换按钮；判定菜单尚未切换，执行切换",
                    flush=True,
                )
                self._click_menu_button()
                trigger = self.wait_for_step(
                    "打开切换菜单",
                    lambda: self._find_for_decision(
                        "紫色 Restart 面板触发按钮（切换后）",
                        Ui.EXIT_PANEL_TRIGGER,
                        Ui.EXIT_PANEL_TRIGGER_REGION,
                    ),
                    profile="panel",
                )
            else:
                print(
                    "[Lineage][菜单判断结论] 已识别到紫色 Restart 面板触发按钮，"
                    "判定菜单已经切换；跳过右下角切换按钮，直接点击紫色按钮",
                    flush=True,
                )
            if trigger is None:
                raise NavigationError("打开切换菜单后仍未找到退出登录触发按钮")
            # 紫色按钮也较小，仅在识别中心一像素范围内做轻微变化。
            self._click(trigger, radius_x=1, radius_y=1)
            relogin = self.wait_for_step(
                "打开 Restart 操作面板",
                lambda: self._find_for_decision(
                    "Restart 操作面板按钮（紫色按钮点击后）",
                    Ui.RELOGIN_BUTTON,
                    Ui.SYSTEM_REGION,
                ),
                profile="panel",
            )
        else:
            print(
                "[Lineage][菜单判断结论] 已识别到 Restart 操作面板按钮，"
                "判定面板已经打开，直接执行 Restart",
                flush=True,
            )
        if relogin is None:
            raise NavigationError("未找到 Restart 按钮")
        print(
            f"[Lineage][切换大区] 点击 Restart，"
            f"coordinate=({relogin[0]},{relogin[1]})",
            flush=True,
        )
        self._click(relogin)
        if not self.wait_for_step(
            "点击 Restart 后进入选择角色界面",
            self._is_character_screen,
            profile="screen",
        ):
            raise NavigationError("点击 Restart 后未进入选择角色界面")

    def _reach_server_screen(self) -> None:
        print("[Lineage][切换大区] 开始进入服务器列表界面", flush=True)
        # 正常交易必须先从游戏主界面执行“重新登录”，再退出角色选择界面。
        # 若上一笔重试已走到角色/服务器界面，则根据实际界面续做，避免倒退。
        if self._trace_screen_probe("当前是否为游戏主界面", self._is_in_game):
            print(
                "[Lineage][切换大区] 当前在游戏主界面，先执行 Restart",
                flush=True,
            )
            self._open_exit_panel_and_relogin()
        elif self._trace_screen_probe("当前是否为角色选择界面", self._is_character_screen):
            print(
                "[Lineage][切换大区] 已在角色选择界面，继续退出到服务器列表",
                flush=True,
            )
        elif self._trace_screen_probe("当前是否为服务器列表", self._is_server_screen):
            print(
                "[Lineage][切换大区] 已在服务器列表，继续未完成的大区选择",
                flush=True,
            )
            return
        else:
            raise NavigationError("当前既不是游戏、选择角色，也不是选择服务器界面")
        exit_button = self._find(
            Ui.CHARACTER_EXIT,
            Ui.CHARACTER_ACTION_REGION,
        )
        if exit_button is None:
            exit_button = self.wait_for_step(
                "查找选择角色界面的 Cancel 按钮",
                lambda: self._find(
                    Ui.CHARACTER_EXIT,
                    Ui.CHARACTER_ACTION_REGION,
                ),
                profile="recognition",
            )
        if exit_button is None:
            raise NavigationError(
                f"连续 {STEP_VERIFY_ATTEMPTS} 次未找到"
                "选择角色界面的 Cancel 按钮"
            )
        print(
            f"[Lineage][切换大区] 点击角色界面 Cancel，"
            f"coordinate=({exit_button[0]},{exit_button[1]})",
            flush=True,
        )
        self._click(exit_button)
        if not self.wait_for_step(
            "退出角色界面后进入服务器列表",
            self._is_server_screen,
            profile="screen",
        ):
            raise NavigationError("退出登录后未进入选择服务器界面")

    def _select_server_page(self, page: int) -> None:
        print(f"[Lineage][切换大区] 准备选择服务器列表第 {page} 页", flush=True)
        if 1 <= page <= Ui.SERVER_VISIBLE_PAGE_COUNT:
            point = (
                Ui.SERVER_PAGE_FIRST_CENTER[0]
                + (page - 1) * Ui.SERVER_PAGE_SPACING_X,
                Ui.SERVER_PAGE_FIRST_CENTER[1],
            )
            source = "800x600 固定分页坐标"
        else:
            point = self.wait_for_step(
                f"定位服务器列表第 {page} 页分页按钮",
                lambda: self.vision.find_page_number(
                    page,
                    Ui.SERVER_PAGINATION_REGION,
                ),
                profile="recognition",
            )
            source = "OCR 定位"
        if point is None:
            raise NavigationError(
                f"连续 {STEP_VERIFY_ATTEMPTS} 次未定位到"
                f"服务器列表第 {page} 页分页按钮；"
                "请确认游戏仍停留在服务器列表，并检查页码是否录入正确"
            )
        print(
            f"[Lineage][切换大区] 点击服务器列表第 {page} 页，"
            f"source={source}，coordinate=({point[0]},{point[1]})",
            flush=True,
        )
        # 分页数字通常较小，限制在识别中心附近的 2px 安全范围。
        self._click(point, radius_x=2, radius_y=2)
        self.wait_after_step(
            f"切换到服务器列表第 {page} 页",
            profile="panel",
        )

    def _select_server(self, target: TargetRegion) -> None:
        # 无法可靠判断当前停留在哪一页，因此每笔交易都显式点击数据库配置页码。
        self._select_server_page(target.select_page)
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
                    f"（已连续检测 {STEP_VERIFY_ATTEMPTS} 次）: "
                    f"{target.name or target.code}"
                )
            source = "OCR 定位"
        if not (left <= point[0] < right and top <= point[1] < bottom):
            raise NavigationError(
                f"大区选择坐标 ({point[0]},{point[1]}) 不在服务器列表安全区域内"
            )
        print(
            f"[Lineage] 选择大区 id={target.region_id} "
            f"target='{_printable(target.name or target.code)}' source={source} "
            f"coordinate=({point[0]},{point[1]})，"
            f"随机偏移=X±{Ui.SERVER_SELECT_RADIUS_X}px/"
            f"Y±{Ui.SERVER_SELECT_RADIUS_Y}px"
        )
        self._click(
            point,
            radius_x=Ui.SERVER_SELECT_RADIUS_X,
            radius_y=Ui.SERVER_SELECT_RADIUS_Y,
        )
        confirm = self.wait_for_step(
            f"选择大区 {_printable(target.name or target.code)} 后等待账号确认页",
            lambda: self._find(
                Ui.ACCOUNT_CONFIRM_BUTTON,
                Ui.ACCOUNT_CONFIRM_REGION,
            ),
            profile="server_connect",
        )
        if confirm is None:
            raise NavigationError("选择大区后未进入账号确认页，或未找到 OK 按钮")
        print(
            f"[Lineage][切换大区] 点击账号确认页 OK，"
            f"coordinate=({confirm[0]},{confirm[1]})",
            flush=True,
        )
        self._click(confirm)
        if not self.wait_for_step(
            "账号确认页点击 OK 后进入选择角色界面",
            self._is_character_screen,
            profile="screen",
        ):
            raise NavigationError("账号确认页点击 OK 后未进入选择角色界面")

    def _select_character_and_login(self) -> None:
        # 角色栏位固定，但人物外观可能变化，因此只点击固定栏位，不识别人像。
        left, top, right, bottom = Ui.CHARACTER_PICK_REGION
        character_point = ((left + right) // 2, (top + bottom) // 2)
        print(
            f"[Lineage][选择角色] 点击固定角色栏位，"
            f"coordinate=({character_point[0]},{character_point[1]})",
            flush=True,
        )
        self._click(character_point, radius_x=12, radius_y=20)
        selected = self.wait_for_step(
            "点击角色后等待资料字段填充",
            self._is_character_selected,
            profile="panel",
        )
        if not selected:
            raise NavigationError("点击固定角色栏位后，角色资料字段仍为空")
        login = self.wait_for_step(
            "选择角色后等待 OK 按钮可用",
            lambda: self._find(Ui.CHARACTER_LOGIN, Ui.CHARACTER_ACTION_REGION),
            profile="panel",
        )
        if login is None:
            raise NavigationError("选择固定角色栏位后未找到可用的 OK 按钮")
        print(
            f"[Lineage][选择角色] 点击 OK 进入游戏，"
            f"coordinate=({login[0]},{login[1]})",
            flush=True,
        )
        self._click(login)
        if not self.wait_for_step(
            "角色登录后进入游戏主界面",
            self._is_in_game,
            profile="screen",
        ):
            raise NavigationError("角色登录后未进入游戏")

    def _is_character_selected(self) -> bool:
        bright_pixels = self.vision.bright_pixel_count(
            Ui.CHARACTER_NAME_VALUE_REGION,
            Ui.CHARACTER_VALUE_BRIGHTNESS,
        )
        selected = bright_pixels >= Ui.CHARACTER_VALUE_MIN_BRIGHT_PIXELS
        print(
            "[Lineage][选择角色] 资料字段检测: "
            f"bright_pixels={bright_pixels}，"
            f"required={Ui.CHARACTER_VALUE_MIN_BRIGHT_PIXELS}，"
            f"selected={'是' if selected else '否'}",
            flush=True,
        )
        return selected

    def ensure_inventory_open(self, *, refresh: bool = False) -> None:
        print(
            "[Lineage][物品栏] 开始检查物品栏打开状态"
            + ("；同区会话复用将先关闭再重开，以刷新上一单残留状态" if refresh else ""),
            flush=True,
        )

        inventory_open = self._find_for_decision(
            "物品栏右侧滚动条与底框",
            Ui.INVENTORY_OPEN,
            Ui.INVENTORY_OPEN_REGION,
            threshold=0.82,
            log_category="物品栏判断",
        )
        if inventory_open is not None:
            print(
                f"[Lineage][物品栏] 已检测到打开状态，"
                f"anchor=({inventory_open[0]},{inventory_open[1]})",
                flush=True,
            )
            if refresh:
                inventory_button = self._find(
                    Ui.INVENTORY_BUTTON,
                    Ui.INVENTORY_BUTTON_REGION,
                )
                if inventory_button is None:
                    inventory_button = Ui.INVENTORY_BUTTON_FALLBACK
                    source = "800x600 固定按钮坐标"
                else:
                    source = "模板定位"
                print(
                    "[Lineage][物品栏] 同区会话命中，先关闭上一单保留的物品栏，"
                    f"source={source}，"
                    f"coordinate=({inventory_button[0]},{inventory_button[1]})",
                    flush=True,
                )
                self._click(inventory_button)
                closed = self.wait_for_step(
                    "同区复用前关闭旧物品栏",
                    lambda: self._find_for_decision(
                        "物品栏右侧滚动条与底框",
                        Ui.INVENTORY_OPEN,
                        Ui.INVENTORY_OPEN_REGION,
                        threshold=0.82,
                        log_category="物品栏刷新",
                    ) is None,
                    profile="panel",
                )
                if not closed:
                    raise InventoryStateError(
                        f"同区会话复用时连续 {STEP_VERIFY_ATTEMPTS} 次"
                        "仍无法关闭上一单保留的物品栏"
                    )
                inventory_open = None
                print(
                    "[Lineage][物品栏] 旧物品栏已关闭，准备重新打开并刷新内容",
                    flush=True,
                )

        if inventory_open is None:
            inventory_button = self._find(
                Ui.INVENTORY_BUTTON,
                Ui.INVENTORY_BUTTON_REGION,
            )
            if inventory_button is None:
                inventory_button = Ui.INVENTORY_BUTTON_FALLBACK
                source = "800x600 固定按钮坐标"
            else:
                source = "模板定位"
            print(
                f"[Lineage][物品栏] 未检测到打开状态，主动点击物品栏按钮，"
                f"source={source}，"
                f"coordinate=({inventory_button[0]},{inventory_button[1]})",
                flush=True,
            )
            self._click(inventory_button)
            inventory_open = self.wait_for_step(
                "主动打开物品栏面板",
                lambda: self._find_for_decision(
                    "物品栏右侧滚动条与底框",
                    Ui.INVENTORY_OPEN,
                    Ui.INVENTORY_OPEN_REGION,
                    threshold=0.82,
                    log_category="物品栏判断",
                ),
                profile="panel",
            )
            if inventory_open is None:
                raise InventoryStateError(
                    f"主动点击物品栏按钮后连续 {STEP_VERIFY_ATTEMPTS} 次"
                    "仍未检测到物品栏打开状态"
                )

        print("[Lineage][物品栏] 已确认物品栏处于打开状态", flush=True)

    def ensure_inventory_items(self, recognition_images: list[str]) -> None:
        if not recognition_images:
            raise NavigationError("订单明细缺少物品识别图片")
        left, top, right, bottom = Ui.INVENTORY_CONTENT_REGION
        print(
            f"[Lineage][物品栏] 开始识别订单物品；"
            f"待识别图片={len(recognition_images)} 张，"
            f"识别区域=X[{left},{right - 1}] Y[{top},{bottom - 1}]",
            flush=True,
        )
        found = self.wait_for_step(
            "物品栏已打开，识别订单物品",
            lambda: self.find_inventory_item(
                recognition_images,
                label="订单物品预检",
            ),
            profile="recognition",
        )
        if not found:
            raise InventoryItemNotFoundError("物品栏已打开，但未识别到订单物品")
        print("[Lineage][物品栏] 已识别到订单物品", flush=True)

    def find_inventory_item(
        self,
        recognition_images,
        *,
        label: str,
    ) -> Optional[tuple[int, int]]:
        """逐张独立识别；任意一张命中即可，单张异常不阻断其余状态图。"""
        images = tuple(dict.fromkeys(
            str(image).strip()
            for image in recognition_images
            if str(image).strip()
        ))
        errors: list[str] = []
        for index, image in enumerate(images, start=1):
            try:
                point = self.vision.find_image(
                    image,
                    Ui.INVENTORY_CONTENT_REGION,
                    threshold=0.90,
                )
            except Exception as exc:
                errors.append(f"{_printable(image)}: {exc}")
                print(
                    f"[Lineage][物品识别] {label} 第 {index}/{len(images)} 张"
                    f"识别异常，继续尝试下一张: image={_printable(image)}，"
                    f"error={exc}",
                    flush=True,
                )
                continue
            print(
                f"[Lineage][物品识别] {label} 第 {index}/{len(images)} 张"
                f"{'命中' if point is not None else '未命中'}: "
                f"image={_printable(image)}"
                + (
                    f"，coordinate=({point[0]},{point[1]})"
                    if point is not None else ""
                ),
                flush=True,
            )
            if point is not None:
                return point
        if images and len(errors) == len(images):
            raise NavigationError(
                f"{label}的全部 {len(images)} 张识别图均加载或识别失败："
                + "；".join(errors)
            )
        return None

    def ensure_target_region(self, order: dict) -> TargetRegion:
        target = TargetRegion.from_order(order)
        cache_key = RegionSessionKey.from_order(
            order,
            target,
            getattr(self.window, "account", ""),
        )
        self.window.focus()

        def client_ready() -> bool:
            self.window.validate_size()
            return True

        if not self.wait_for_step(
            "激活并确认游戏客户区可操作",
            client_ready,
            profile="screen",
        ):
            raise NavigationError(
                f"激活游戏窗口后连续 {STEP_VERIFY_ATTEMPTS} 次"
                "仍无法确认客户区可操作"
            )

        cache_hit = (
            self.region_session_cache is not None
            and self.region_session_cache.matches(cache_key)
        )
        reuse_region = False
        if cache_hit:
            print(
                "[Lineage][大区缓存] 命中已登录大区: "
                f"id={target.region_id} "
                f"name={_printable(target.name or target.code)}，"
                "开始确认游戏主界面",
                flush=True,
            )
            reuse_region = self._trace_screen_probe(
                "缓存大区是否仍在游戏主界面",
                self._is_in_game,
            )
            if reuse_region:
                print(
                    "[Lineage][大区缓存] 当前仍在订单大区，"
                    "跳过 Restart、选服和角色重新登录",
                    flush=True,
                )
            else:
                self.region_session_cache.invalidate()
                print(
                    "[Lineage][大区缓存] 缓存对应的游戏会话已失效，"
                    "本次重新选择大区并登录",
                    flush=True,
                )
        elif self.region_session_cache is not None:
            previous = self.region_session_cache.invalidate()
            if previous is None:
                reason = "尚无成功登录记录"
            elif previous.region_id != target.region_id:
                reason = (
                    f"订单大区已变化（缓存 region_id={previous.region_id}，"
                    f"订单 region_id={target.region_id}）"
                )
            else:
                reason = "游戏、账号或窗口会话标识已变化，不能复用大区登录缓存"
            print(
                f"[Lineage][大区缓存] 未命中: {reason}",
                flush=True,
            )

        def login_target_region() -> None:
            print(
                "[Lineage] 准备选择订单大区: "
                f"{_printable(target.name or target.code)}，"
                f"页码={target.select_page}",
                flush=True,
            )
            try:
                self._reach_server_screen()
                self._select_server(target)
                self._select_character_and_login()
            except Exception:
                if self.region_session_cache is not None:
                    self.region_session_cache.invalidate()
                raise
            if self.region_session_cache is not None:
                self.region_session_cache.remember(cache_key)
                print(
                    "[Lineage][大区缓存] 大区登录成功，已缓存: "
                    f"id={target.region_id} "
                    f"name={_printable(target.name or target.code)}",
                    flush=True,
                )

        if not reuse_region:
            login_target_region()

        recognition_images = list(dict.fromkeys(
            image
            for detail in (order.get("details") or [])
            for image in item_recognition_images(detail)
        ))

        def prepare_inventory(*, refresh: bool) -> None:
            print(
                "[Lineage][流程衔接] 已进入游戏主界面，先检查并打开物品栏",
                flush=True,
            )
            self.ensure_inventory_open(refresh=refresh)
            print(
                "[Lineage][流程衔接] 物品栏已打开，开始整理订单物品识别信息",
                flush=True,
            )
            self.ensure_inventory_items(recognition_images)

        try:
            prepare_inventory(refresh=reuse_region)
        except (InventoryStateError, InventoryItemNotFoundError) as exc:
            if not reuse_region:
                raise
            if self.region_session_cache is not None:
                self.region_session_cache.invalidate()
            print(
                "[Lineage][大区缓存] 同区会话刷新后仍无法可靠识别物品，"
                f"自动执行一次完整登录恢复: {exc}",
                flush=True,
            )
            login_target_region()
            prepare_inventory(refresh=False)

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
    region_session_cache: Optional[RegionSessionCache] = None,
) -> LineageSessionNavigator:
    window = ClientWindow.find(account=account)
    return LineageSessionNavigator(
        hardware=hardware,
        window=window,
        vision=TemplateVision(window),
        runtime_status=runtime_status,
        cancelled=cancelled,
        input_controller=input_controller,
        region_session_cache=region_session_cache,
    )
