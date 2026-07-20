"""
天堂经典版（Lineage Classic）自动交易 —— 演示脚本（Demo / Dry-Run）。

流程：
    1. 识别游戏窗口，并将窗口置于最上层
    2. 判断当前窗口状态，若为“已登录”状态则继续
    3. 等待特定位置出现交易弹窗
    4. 弹窗出现后点击 [Yes]，自动进入交易界面
    5. 点击金币图标
    6. 将金币拖动到指定位置后松开
    7. 点击特定位置的输入框
    8. 输入外部传入的数字（交易金额/数量）
    9. 按下回车
    10. 截图保存当前界面
    11. 点击特定位置的 [OK]
    12. 等待片刻后点击特定位置的 [Yes]
    13. 再等待片刻，判断交易是否完成

重要：本脚本为演示用途，**不会真正移动鼠标或点击**，
      每一步仅打印出“点击的位置”或“鼠标移动轨迹”。

运行：
    python -m trader.executor.lineage_classic_demo 1000000
    （最后的数字为要输入的交易参数，可省略，默认 1000000）
"""
import math
import sys
import time
from typing import List, Optional, Tuple

# pywin32 按需导入（真实模式才需要，Dry-Run 不需要）
try:
    import win32gui
    import win32con
    _HAS_WIN32 = True
except ImportError:
    _HAS_WIN32 = False

# OpenCV / Pillow 按需导入（真实模式才需要屏幕捕获 + 模板匹配）
try:
    import cv2
    import numpy as np
    from PIL import ImageGrab
    _HAS_CV = True
except ImportError:
    _HAS_CV = False


# ─────────────────────────────────────────────────────────────
# 演示用坐标常量（相对屏幕像素，可按实际分辨率调整）
# ─────────────────────────────────────────────────────────────
class Coord:
    """交易流程中涉及的关键界面坐标（演示值）。"""

    # 交易弹窗上的 [Yes] 按钮
    TRADE_POPUP_YES = (640, 380)
    # 交易界面中的金币图标（拖动起点）
    GOLD_ICON = (512, 460)
    # 金币拖动的目标位置（交易槽）
    GOLD_DROP_SLOT = (760, 300)
    # 数量/金额输入框
    AMOUNT_INPUT = (760, 360)
    # 确认交易的 [OK] 按钮
    CONFIRM_OK = (700, 520)
    # 二次确认的 [Yes] 按钮
    CONFIRM_YES = (660, 470)

    # 用于识别"交易弹窗是否出现"的检测区域（左上、右下）
    TRADE_POPUP_REGION = ((560, 340), (720, 420))
    
    # 模板图片存放目录（相对于 worker 目录）
    TEMPLATE_DIR = "templates/lineage_classic"
    # 各步骤需要的模板文件名
    TPL_TRADE_POPUP = "trade_popup.png"       # 交易弹窗的特征区域截图（如 Yes 按钮）
    TPL_TRADE_FINISHED = "trade_finished.png"   # 交易完成后的特征（如"交易成功"文字）
    TPL_LOGGED_IN = "logged_in.png"             # 已登录界面的特征（如角色HUD/HP条）
    
    # 模板匹配阈值（0~1，越高越严格）
    MATCH_THRESHOLD = 0.85


# ─────────────────────────────────────────────────────────────
# 真实窗口管理器（通过 Windows API 查找并置顶游戏窗口）
# ─────────────────────────────────────────────────────────────
class WindowManager:
    """Windows 原生窗口管理 —— 查找 / 置顶 / 获取区域。

    依赖 pywin32： pip install pywin32
    """

    @staticmethod
    def find_by_title(keyword: str) -> Optional[int]:
        """模糊匹配窗口标题，返回窗口句柄（hwnd）。

        天堂经典版的窗口标题通常包含「天堂」或英文名。
        """
        if not _HAS_WIN32:
            return None
        matches = []

        def _enum_callback(hwnd: int, _extra):
            if not win32gui.IsWindowVisible(hwnd):
                return
            title = win32gui.GetWindowText(hwnd)
            if keyword in title:
                matches.append((hwnd, title))

        win32gui.EnumWindows(_enum_callback, None)

        if not matches:
            # 尝试精确类名查找（Lineage 客户端的窗口类名通常是固定值）
            # 可用 Spy++ 或 WinLister 工具获取准确的类名
            hwnd = win32gui.FindWindow("LineageWindow", None)  # ← 需实测确认
            if hwnd:
                title = win32gui.GetWindowText(hwnd)
                matches.append((hwnd, title))

        for hwnd, title in matches:
            print(f"[窗口管理] 候选窗口: hwnd={hwnd} title='{title}'")

        return matches[0][0] if matches else None

    @staticmethod
    def get_rect(hwnd: int) -> Tuple[int, int, int, int]:
        """返回窗口矩形: (left, top, right, bottom)。

        注意：返回的是相对于屏幕左上角的绝对像素坐标。
        后续所有鼠标点击坐标都应以 left/top 为基准偏移计算。
        """
        if not _HAS_WIN32:
            return (100, 80, 1124, 848)  # fallback
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        return (left, top, right, bottom)

    @staticmethod
    def focus(hwnd: int) -> bool:
        """将窗口拉到最前端。"""
        if not _HAS_WIN32:
            return False
        # 如果窗口最小化，先还原
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.3)  # 等系统完成窗口切换动画
        return True

    @staticmethod
    def find_and_focus(keyword: str = "天堂") -> Optional[Tuple[int, int, int, int]]:
        """一站式：查找 + 置顶 + 返回区域。

        Returns:
            (left, top, right, bottom) 绝对坐标，或 None 表示未找到。
        """
        hwnd = WindowManager.find_by_title(keyword)
        if hwnd is None:
            print(f"[窗口管理] 未找到标题含 '{keyword}' 的窗口！")
            return None
        print(f"[窗口管理] 找到窗口 hwnd={hwnd}")
        WindowManager.focus(hwnd)
        rect = WindowManager.get_rect(hwnd)
        left, top, right, bottom = rect
        w, h = right - left, bottom - top
        print(f"[窗口管理] 窗口区域: left={left}, top={top}, width={w}, height={h}")
        return rect


# ─────────────────────────────────────────────────────────────
# 屏幕捕获 + 图像模板匹配工具
# ─────────────────────────────────────────────────────────────
class ScreenCapture:
    """屏幕截图 + OpenCV 模板匹配。

    依赖： pip install opencv-python Pillow numpy

    模板准备步骤：
        1. 启动天堂经典版，到达需要检测的界面（如交易弹窗出现时）
        2. 截一张完整屏幕截图
        3. 用画图工具裁剪出目标元素（如 Yes 按钮、"交易成功"文字区域）
        4. 保存到 worker/templates/lineage_classic/ 下，文件名与 Coord.TPL_* 一致
    """

    _template_cache: dict = {}  # 缓存已加载的模板灰度图，避免重复读盘

    @staticmethod
    def _template_path(name: str) -> str:
        import os
        base = os.path.dirname(os.path.abspath(__file__))
        worker_dir = os.path.dirname(os.path.dirname(os.path.dirname(base)))
        return os.path.join(worker_dir, Coord.TEMPLATE_DIR, name)

    @staticmethod
    def capture(region: Optional[Tuple[int, int, int, int]] = None) -> "np.ndarray":
        """截取屏幕指定区域，返回 BGR 格式 numpy 数组（OpenCV 格式）。

        Args:
            region: (left, top, right, bottom) 屏幕绝对像素坐标，None 则截全屏。
        """
        if not _HAS_CV:
            return np.zeros((100, 100, 3), dtype=np.uint8)
        img = ImageGrab.grab(bbox=region, all_screens=True)
        return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

    @staticmethod
    def save(path: str, region: Optional[Tuple[int, int, int, int]] = None) -> str:
        """截图并保存到文件，返回文件路径。"""
        import os
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        if _HAS_CV:
            img = ImageGrab.grab(bbox=region, all_screens=True)
            img.save(path)
            print(f"[截图] 已保存: {path}")
        else:
            print(f"[截图] [Dry-Run] 未真正保存: {path}")
        return path

    @staticmethod
    def match_template(
        tpl_name: str,
        region: Optional[Tuple[int, int, int, int]] = None,
        threshold: float = Coord.MATCH_THRESHOLD,
    ) -> Optional[Tuple[int, int]]:
        """在屏幕指定区域内搜索模板图片，返回匹配中心坐标。

        原理：OpenCV TM_CCOEFF_NORMED ——
            对截图区域做滑动窗口，计算每个位置与模板的归一化相关系数，
            系数越接近 1.0 表示越匹配。

        Args:
            tpl_name: 模板文件名（如 Coord.TPL_TRADE_POPUP）
            region: 搜索区域 (left, top, right, bottom)，None 则全屏搜索
            threshold: 匹配阈值 0~1，低于此值认为未找到

        Returns:
            (center_x, center_y) 相对于屏幕左上角的绝对坐标，或 None 表示未匹配。
        """
        if not _HAS_CV:
            return None

        # 加载模板（带缓存，只加载一次）
        if tpl_name not in ScreenCapture._template_cache:
            tpl_path = ScreenCapture._template_path(tpl_name)
            import os as _os
            if not _os.path.exists(tpl_path):
                print(f"[模板匹配] 模板文件不存在: {tpl_path}")
                return None
            ScreenCapture._template_cache[tpl_name] = cv2.imread(tpl_path, cv2.IMREAD_COLOR)

        template = ScreenCapture._template_cache[tpl_name]
        tpl_h, tpl_w = template.shape[:2]

        # 截图搜索区域
        screen = ScreenCapture.capture(region)
        if screen.size == 0:
            return None
        if screen.shape[0] < tpl_h or screen.shape[1] < tpl_w:
            print(f"[模板匹配] 搜索区域({screen.shape[1]}x{screen.shape[0]})小于模板({tpl_w}x{tpl_h})")
            return None

        # 模板匹配
        result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        if max_val < threshold:
            print(f"[模板匹配] 未匹配到 '{tpl_name}' (max_val={max_val:.3f} < threshold={threshold})")
            return None

        # 计算匹配中心在屏幕上的绝对坐标
        center_x = (max_loc[0] + tpl_w // 2) + (region[0] if region else 0)
        center_y = (max_loc[1] + tpl_h // 2) + (region[1] if region else 0)
        print(f"[模板匹配] 匹配到 '{tpl_name}' center=({center_x},{center_y}) confidence={max_val:.3f}")
        return (center_x, center_y)


# ─────────────────────────────────────────────────────────────
# Dry-Run 硬件控制器：只输出动作，不执行任何真实键鼠操作
# ─────────────────────────────────────────────────────────────
class DryRunHardwareController:
    """演示用键鼠控制器。

    接口与 trader.executor.hardware.controller.HardwareController 保持一致，
    但所有动作仅打印“位置 / 轨迹”，绝不发送任何真实指令。
    """

    def __init__(self):
        self._cursor: Tuple[int, int] = (0, 0)

    # ── 轨迹生成 ──
    @staticmethod
    def _bezier_trajectory(
        start: Tuple[int, int],
        end: Tuple[int, int],
        steps: int = 12,
    ) -> List[Tuple[int, int]]:
        """生成一条二次贝塞尔曲线轨迹点（模拟人类移动）。"""
        sx, sy = start
        ex, ey = end
        # 控制点：取中点并施加一定偏移，形成弧线
        cx = (sx + ex) / 2 + (ey - sy) * 0.2
        cy = (sy + ey) / 2 - (ex - sx) * 0.2
        points: List[Tuple[int, int]] = []
        for i in range(steps + 1):
            t = i / steps
            # 缓入缓出，使首尾速度更慢，更像人手
            t = t * t * (3 - 2 * t)
            x = (1 - t) ** 2 * sx + 2 * (1 - t) * t * cx + t ** 2 * ex
            y = (1 - t) ** 2 * sy + 2 * (1 - t) * t * cy + t ** 2 * ey
            points.append((round(x), round(y)))
        return points

    # ── 鼠标操作 ──
    def mouse_move(self, x: int, y: int) -> List[Tuple[int, int]]:
        """[Dry-Run] 输出从当前光标到目标点的移动轨迹。"""
        traj = self._bezier_trajectory(self._cursor, (x, y))
        traj_str = " → ".join(f"({px},{py})" for px, py in traj)
        print(f"[鼠标移动] 轨迹: {traj_str}")
        self._cursor = (x, y)
        return traj

    def mouse_click(self, x: int, y: int, button: str = "left") -> None:
        """[Dry-Run] 移动到目标点并输出点击位置。"""
        self.mouse_move(x, y)
        print(f"[鼠标点击] 位置: ({x}, {y})  按键: {button}")

    def mouse_drag(self, x1: int, y1: int, x2: int, y2: int) -> None:
        """[Dry-Run] 输出拖拽的按下点、拖动轨迹、松开点。"""
        self.mouse_move(x1, y1)
        print(f"[鼠标按下] 位置: ({x1}, {y1})")
        traj = self._bezier_trajectory((x1, y1), (x2, y2))
        traj_str = " → ".join(f"({px},{py})" for px, py in traj)
        print(f"[鼠标拖动] 轨迹: {traj_str}")
        print(f"[鼠标松开] 位置: ({x2}, {y2})")
        self._cursor = (x2, y2)

    # ── 键盘操作 ──
    def key_type(self, text: str) -> None:
        """[Dry-Run] 输出逐字输入的文本。"""
        print(f"[键盘输入] 文本: '{text}'  (逐字: {' '.join(list(text))})")

    def key_press(self, key: str) -> None:
        """[Dry-Run] 输出按键。"""
        print(f"[键盘按键] 按下: {key}")


# ─────────────────────────────────────────────────────────────
# 天堂经典版交易执行器（演示版）
# ─────────────────────────────────────────────────────────────
class LineageClassicDemoExecutor:
    """天堂经典版自动交易流程演示。

    所有窗口/图像识别均为模拟返回，键鼠操作全部走 Dry-Run。
    """

    game_code = "lineage_classic"

    def __init__(self, hw: DryRunHardwareController):
        self._hw = hw
        self._step = 0

    # ── 辅助：步骤打印 ──
    def _log_step(self, title: str) -> None:
        self._step += 1
        print(f"\n──── 步骤 {self._step}：{title} ────")

    def _wait(self, seconds: float, reason: str) -> None:
        print(f"[等待] {seconds:.1f}s —— {reason}")
        # 演示环境下缩短真实等待，避免长时间阻塞
        time.sleep(min(seconds, 0.3))

    # ── 步骤 1：识别并置顶游戏窗口 ──
    def find_and_focus_window(self) -> Tuple[int, int, int, int]:
        self._log_step("识别游戏窗口并置顶")

        if _HAS_WIN32:
            # ── 真实模式：通过 Windows API 查找 ──
            rect = WindowManager.find_and_focus("天堂")
            if rect is None:
                # 尝试其他可能的标题（韩服 / 台服标题不同）
                rect = WindowManager.find_and_focus("Lineage")
            if rect is None:
                raise RuntimeError("未找到天堂经典版游戏窗口！请确认游戏已启动。")
            left, top, right, bottom = rect
            w, h = right - left, bottom - top
            print(f"[窗口识别] 找到窗口 '天堂经典版'  hwnd 区域: "
                  f"left={left}, top={top}, width={w}, height={h}")
            return (left, top, w, h)
        else:
            # ── 演示模式：返回固定坐标（未安装 pywin32） ──
            rect = (100, 80, 1024, 768)
            print(f"[窗口识别] 找到窗口 '天堂经典版'  区域: left={rect[0]}, "
                  f"top={rect[1]}, width={rect[2]}, height={rect[3]}")
            print("[窗口置顶] 将窗口设置为最前端 (SetForegroundWindow / BringToTop)")
            return rect

    # ── 步骤 2：判断登录状态 ──
    def check_logged_in(self) -> bool:
        self._log_step("判断当前窗口状态")
        if _HAS_CV:
            # 真实模式：在窗口区域内搜索"已登录"特征（如角色HUD/HP条）
            found = ScreenCapture.match_template(
                Coord.TPL_LOGGED_IN,
                region=None,  # 全屏搜索
            )
            logged_in = found is not None
        else:
            # 演示模式
            logged_in = True
        state = "已登录" if logged_in else "未登录/登录界面"
        print(f"[状态判断] 当前窗口状态: {state}")
        return logged_in

    # ── 步骤 3：等待交易弹窗出现 ──
    def wait_for_trade_popup(self, timeout_s: float = 30.0) -> bool:
        self._log_step("等待特定位置出现交易弹窗")
        (x1, y1), (x2, y2) = Coord.TRADE_POPUP_REGION
        search_region = (x1, y1, x2, y2)
        print(f"[弹窗检测] 监视区域: 左上({x1},{y1}) 右下({x2},{y2})")

        if _HAS_CV:
            # 真实模式：轮询截图 + 模板匹配
            poll_interval = 0.5  # 每 0.5 秒检测一次
            deadline = time.time() + timeout_s
            while time.time() < deadline:
                found = ScreenCapture.match_template(
                    Coord.TPL_TRADE_POPUP,
                    region=search_region,
                )
                if found is not None:
                    print("[弹窗检测] 检测到交易弹窗！")
                    return True
                print(f"[弹窗检测] 未检测到弹窗，{poll_interval}s 后重试...")
                time.sleep(poll_interval)
            print(f"[弹窗检测] 超时({timeout_s}s)，未检测到交易弹窗")
            return False
        else:
            # 演示模式：直接返回成功
            self._wait(1.0, "轮询检测弹窗是否出现")
            print("[弹窗检测] 检测到交易弹窗！")
            return True

    # ── 步骤 4~13：核心交易流程 ──
    def run_trade(self, amount: int) -> dict:
        # 步骤 4：点击弹窗上的 Yes
        self._log_step("点击交易弹窗 [Yes]")
        self._hw.mouse_click(*Coord.TRADE_POPUP_YES)
        self._wait(0.8, "等待交易界面打开")
        print("[界面识别] 交易界面已自动出现")

        # 步骤 5：点击金币图标
        self._log_step("点击金币图标")
        self._hw.mouse_click(*Coord.GOLD_ICON)

        # 步骤 6：拖动金币到指定位置后松开
        self._log_step("拖动金币到交易槽后松开")
        gx, gy = Coord.GOLD_ICON
        dx, dy = Coord.GOLD_DROP_SLOT
        self._hw.mouse_drag(gx, gy, dx, dy)

        # 步骤 7：点击输入框
        self._log_step("点击数量/金额输入框")
        self._hw.mouse_click(*Coord.AMOUNT_INPUT)

        # 步骤 8：输入数字
        self._log_step("输入交易参数")
        self._hw.key_type(str(amount))

        # 步骤 9：按回车
        self._log_step("按下回车确认输入")
        self._hw.key_press("Enter")

        # 步骤 10：截图保存
        self._log_step("截图保存当前界面")
        shot_path = self._save_screenshot()

        # 步骤 11：点击 OK
        self._log_step("点击 [OK] 确认")
        self._hw.mouse_click(*Coord.CONFIRM_OK)

        # 步骤 12：等待后点击 Yes
        self._log_step("等待后点击二次确认 [Yes]")
        self._wait(1.0, "等待二次确认弹窗出现")
        self._hw.mouse_click(*Coord.CONFIRM_YES)

        # 步骤 13：等待并判断交易结果
        self._log_step("等待并判断交易是否完成")
        self._wait(1.5, "等待交易结算")
        success = self._check_trade_finished()

        return {
            "success": success,
            "amount": amount,
            "screenshot": shot_path,
        }

    # ── 演示用：截图 & 结果判断 ──
    def _save_screenshot(self) -> str:
        ts = time.strftime("%Y%m%d_%H%M%S")
        path = f"screenshots/trade_{ts}.png"
        if _HAS_CV:
            # 真实截图：截取交易界面周边区域（避免保存不必要的全屏内容）
            (x1, y1), (x2, y2) = Coord.TRADE_POPUP_REGION
            ScreenCapture.save(path, region=(x1 - 100, y1 - 50, x2 + 100, y2 + 300))
        else:
            print(f"[截图] [Dry-Run] 未真正保存: {path}")
        return path

    def _check_trade_finished(self) -> bool:
        if _HAS_CV:
            # 真实模式：搜索"交易完成"特征（如"交易成功"提示文字）
            found = ScreenCapture.match_template(
                Coord.TPL_TRADE_FINISHED,
                region=None,
            )
            finished = found is not None
        else:
            # 演示模式
            finished = True
        print(f"[结果判断] 交易状态: {'已完成' if finished else '未完成'}")
        return finished

    # ── 完整流程编排 ──
    def execute(self, amount: int) -> dict:
        print("=" * 56)
        print(f"  天堂经典版自动交易 Demo（Dry-Run） amount={amount}")
        print("=" * 56)

        self.find_and_focus_window()

        if not self.check_logged_in():
            print("\n[中止] 当前不是已登录状态，流程结束。")
            return {"success": False, "reason": "not_logged_in"}

        if not self.wait_for_trade_popup():
            print("\n[中止] 等待交易弹窗超时，流程结束。")
            return {"success": False, "reason": "popup_timeout"}

        result = self.run_trade(amount)

        print("\n" + "=" * 56)
        print(f"  流程结束，结果: {result}")
        print("=" * 56)
        return result


def main():
    # 解析外部传入的交易参数（数字）
    amount = 1_000_000
    if len(sys.argv) > 1:
        try:
            amount = int(sys.argv[1])
        except ValueError:
            print(f"[警告] 参数 '{sys.argv[1]}' 不是有效数字，使用默认值 {amount}")

    hw = DryRunHardwareController()
    executor = LineageClassicDemoExecutor(hw)
    executor.execute(amount)


if __name__ == "__main__":
    main()
