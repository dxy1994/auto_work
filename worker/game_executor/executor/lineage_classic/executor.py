"""Lineage Classic 正式交易执行器。"""

from __future__ import annotations

import asyncio
import threading
import time
import uuid
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Callable, Optional

from game_executor.executor.base import BaseGameExecutor
from game_executor.executor.hardware.humanized import HumanizedInputController
from game_executor.executor.lineage_classic.navigation import (
    ClientWindow,
    NavigationCancelled,
    NavigationError,
    LineageSessionNavigator,
    TemplateVision,
    Ui,
    build_navigator,
    item_recognition_images,
)
from game_executor.executor.lineage_classic.policy import (
    buyer_poll_schedule,
    trade_timeout_seconds,
)


class TradeUi:
    # 交易申请整行会随买家名长度横向移动，只有右下角 Yes/No 基本固定。
    # 先识别 Yes/No 确认弹窗存在，再单独 OCR 左侧买家名；聊天框文字
    # 不能作为交易申请出现的依据。
    REQUEST_TEMPLATE = "交易弹窗提醒.png"
    CONFIRM_BUTTON_TEMPLATE = "交易确认按钮.png"
    CANCEL_BUTTON_TEMPLATE = "交易取消按钮.png"
    FINAL_CONFIRM_TEMPLATE = "最终确认交易判断.png"
    REQUEST_TEMPLATE_REGION = (515, 535, 595, 565)
    CUSTOMER_NAME_REGION = (144, 516, 241, 538)
    REQUEST_ACCEPT_REGION = (528, 547, 547, 556)
    REQUEST_REJECT_REGION = (561, 547, 575, 556)
    TRADE_WINDOW_REGION = (0, 0, 235, 360)
    MY_TRADE_REGION = (22, 38, 190, 166)
    MY_TRADE_DROP_REGION = (50, 65, 162, 140)
    BUYER_TRADE_REGION = (22, 203, 190, 330)
    TRADE_ACTION_REGION = (120, 330, 225, 360)
    # 兼容仍引用旧名称的扩展代码。
    BOTH_TRADE_REGION = TRADE_WINDOW_REGION
    FINAL_ACCEPT_REGION = (528, 547, 547, 556)
    FINAL_REJECT_REGION = (561, 547, 575, 556)
    REQUEST_REVIEW_SCREENSHOT_REGION = (120, 490, 590, 570)


@dataclass(frozen=True)
class TradeTransfer:
    source: tuple[int, int]
    quantity: int
    label: str


def region_center(region: tuple[int, int, int, int]) -> tuple[int, int]:
    left, top, right, bottom = region
    return (left + right) // 2, (top + bottom) // 2


def random_region_point(
    region: tuple[int, int, int, int],
    random_uniform: Callable[[float, float], float],
) -> tuple[int, int]:
    """在区域内生成可复现注入的随机落点，右、下边界不包含。"""
    left, top, right, bottom = region
    if right <= left or bottom <= top:
        raise ValueError(f"无效区域: {region}")
    x = int(round(random_uniform(left, right - 1)))
    y = int(round(random_uniform(top, bottom - 1)))
    return (
        min(right - 1, max(left, x)),
        min(bottom - 1, max(top, y)),
    )


def _normalized_customer_name(value: object) -> str:
    return "".join(ch.casefold() for ch in str(value or "") if ch.isalnum())


def customer_name_prefix_matches(observed: str, expected: str) -> bool:
    """韩语主格助词 이、가、이[가] 等会跟在角色名后，只校验后台客户名前缀。"""
    actual = _normalized_customer_name(observed)
    prefix = _normalized_customer_name(expected)
    return bool(actual and prefix and actual.startswith(prefix))


def buyer_ocr_action(observed: str, expected: str, confidence: float) -> str:
    """只有 90 分及以上且前缀匹配才自动接受，其余情况全部交给人工。"""
    if confidence >= 90.0 and customer_name_prefix_matches(observed, expected):
        return "accept"
    return "review"


class LineageClassicExecutor(BaseGameExecutor):
    """完成切区、等待交易请求和金币交易操作。

    同步 Win32/图像/硬件调用放在独立线程，不占用 WebSocket 事件循环。
    """

    game_code = "리니지클래식"
    game_codes = ("리니지클래식", "lineage_classic", "lineage classic")
    game_name = "天堂经典版"

    def __init__(self, hw, runtime_status=None):
        self._cancel_event = threading.Event()
        super().__init__(hw)
        self._input = HumanizedInputController(
            hw,
            cancelled=self._cancel_event.is_set,
        )
        self._runtime_status = runtime_status
        self._progress: Optional[Callable[[str, str], None]] = None
        self._buyer_review_callback: Optional[Callable[[dict], None]] = None
        self._trade_screenshot_callback: Optional[Callable[[str], bool]] = None
        self._review_condition = threading.Condition()
        self._pending_review_id: Optional[str] = None
        self._review_decision: Optional[bool] = None
        self._phase = "idle"
        self._runtime_recovery_pending = False

    def set_progress_callback(self, callback: Optional[Callable[[str, str], None]]) -> None:
        self._progress = callback

    def set_buyer_review_callback(self, callback: Optional[Callable[[dict], None]]) -> None:
        self._buyer_review_callback = callback

    def set_trade_screenshot_callback(self, callback: Optional[Callable[[str], bool]]) -> None:
        self._trade_screenshot_callback = callback

    def submit_buyer_review(self, review_id: str, approved: bool) -> bool:
        with self._review_condition:
            if not review_id or review_id != self._pending_review_id:
                return False
            self._review_decision = bool(approved)
            self._review_condition.notify_all()
            return True

    def cancel(self):
        self._cancel_event.set()
        with self._review_condition:
            self._review_condition.notify_all()

    def runtime_recovery_pending(self) -> bool:
        """连接检查是否已实际尝试恢复窗口、但仍需要有限次数重试。"""
        return self._runtime_recovery_pending

    def probe_runtime(self) -> bool:
        """连接检查唯一的天堂窗口；只自动恢复最小化窗口，不在空闲期选服。"""
        recoverable = False
        self._runtime_recovery_pending = False
        print("[Lineage] 开始检查天堂经典版游戏运行状态")
        try:
            window = ClientWindow.find()
            size = window.client_size()
            print(f"[Lineage] 已找到游戏窗口，当前客户区 {size[0]}x{size[1]}")
            if size == (0, 0):
                print("[Lineage] 检测到游戏窗口最小化（客户区 0x0），正在自动恢复")
                recoverable = True
                self._runtime_recovery_pending = True
                try:
                    size = window.restore()
                except NavigationError as exc:
                    print(
                        f"[Lineage] 游戏窗口本次自动恢复未完成: {exc}，"
                        "将进行连接后的有限次数恢复重试"
                    )
                    size = (0, 0)

                if size == (0, 0):
                    print(
                        "[Lineage] 游戏窗口本次自动恢复未完成（客户区仍为 0x0），"
                        "将进行连接后的有限次数恢复重试"
                    )
                else:
                    self._runtime_recovery_pending = False
                    print(
                        f"[Lineage] 游戏窗口已自动恢复，客户区 {size[0]}x{size[1]}，"
                        "继续检查登录界面"
                    )
                    try:
                        window.focus()
                    except NavigationError as exc:
                        self._runtime_recovery_pending = True
                        print(
                            f"[Lineage] 游戏窗口已恢复但本次无法切换到前台: {exc}，"
                            "将进行连接后的有限次数恢复重试"
                        )
                        size = (0, 0)

            if size == (0, 0):
                ready = False
            else:
                # 使用同一次读取结果校验，避免校验过程中窗口状态变化把 0x0 误判为永久异常。
                window.validate_size(size)
                navigator = LineageSessionNavigator(
                    self._hw,
                    window,
                    TemplateVision(window),
                    runtime_status=self._runtime_status,
                    input_controller=self._input,
                )
                ready = navigator._is_in_game()
                if ready:
                    print("[Lineage] 天堂经典版已处于游戏主界面，运行状态正常")
                else:
                    # 没有订单时缺少目标大区，不能在连接检查阶段自行选服。
                    recoverable = True
                    print(
                        "[Lineage] 游戏窗口可操作，但当前不在游戏主界面；"
                        "空闲期不会自动选择大区，将在收到交易任务后按订单信息恢复"
                    )
        except NavigationError as exc:
            print(f"[Lineage] 运行态检查失败: {exc}")
            ready = False
        if self._runtime_status is not None:
            self._runtime_status.update(
                client_status="logged_in" if ready else "not_ready",
                ui_health="ready" if ready else "recoverable" if recoverable else "unhealthy",
            )
        return ready

    async def execute(self, order: dict) -> dict:
        self._cancel_event.clear()
        self._phase = "preparing"
        started = time.monotonic()
        try:
            result = await asyncio.to_thread(self._execute_sync, order)
        except NavigationCancelled:
            if self._phase in {"trading", "verifying"}:
                result = self._result(
                    False,
                    "verification_failed",
                    "TRADE_CANCELLED_RESULT_UNCERTAIN",
                    "交易操作中收到取消，结果需要人工复核",
                )
            else:
                result = self._result(False, "cancelled", "TRADE_CANCELLED", "交易已取消")
        except NavigationError as exc:
            if self._phase in {"trading", "verifying"}:
                result = self._result(
                    False, "verification_failed", "TRADE_RESULT_UNCERTAIN", str(exc)
                )
            else:
                result = self._result(
                    False, "retryable_failed", "GAME_PREPARATION_FAILED", str(exc)
                )
        except Exception as exc:
            terminal = "verification_failed" if self._phase in {"trading", "verifying"} else "failed"
            error_code = "TRADE_RESULT_UNCERTAIN" if terminal == "verification_failed" else "EXECUTOR_EXCEPTION"
            result = self._result(False, terminal, error_code, str(exc))
        result["duration_ms"] = int((time.monotonic() - started) * 1000)
        return result

    def _execute_sync(self, order: dict) -> dict:
        self._emit("preparing", "正在检查天堂经典版客户端")
        navigator = build_navigator(
            self._hw,
            runtime_status=self._runtime_status,
            cancelled=self._cancel_event.is_set,
            input_controller=self._input,
        )

        self._emit("switching_region", "正在确认并切换到订单大区")
        navigator.ensure_target_region(order)

        self._emit("waiting_buyer", "已进入目标大区，等待买家交易申请")
        expected_buyer = str(order.get("buyer_character") or "").strip()
        if not expected_buyer:
            return self._result(
                False,
                "failed",
                "BUYER_CHARACTER_MISSING",
                "订单缺少买家角色名，不能安全接受交易",
            )
        observed_buyer = self._wait_for_expected_buyer(
            navigator,
            expected_buyer,
            timeout=trade_timeout_seconds(order),
        )
        if observed_buyer is None:
            return self._result(
                False,
                "timed_out",
                "TRADE_REQUEST_TIMEOUT",
                "等待买家交易申请超时",
            )

        transfers = self._build_transfers(order, navigator)

        self._emit(
            "trading",
            f"已核验买家 {observed_buyer}，正在放入 {len(transfers)} 项交易资产",
        )
        navigator.click_region(TradeUi.REQUEST_ACCEPT_REGION)
        trade_cancel = navigator.wait_for_step(
            "接受买家申请后进入交易界面",
            lambda: navigator.vision.find(
                TradeUi.CANCEL_BUTTON_TEMPLATE,
                TradeUi.TRADE_ACTION_REGION,
                threshold=0.90,
            ),
            profile="screen",
            fixed_wait=1.0,
        )
        if trade_cancel is None:
            raise NavigationError("接受申请后未识别到交易界面")

        print(
            "[Lineage][交易界面] 已确认交易窗口；"
            f"我方物品区=X[{TradeUi.MY_TRADE_REGION[0]},{TradeUi.MY_TRADE_REGION[2] - 1}] "
            f"Y[{TradeUi.MY_TRADE_REGION[1]},{TradeUi.MY_TRADE_REGION[3] - 1}]，"
            f"买方物品区=X[{TradeUi.BUYER_TRADE_REGION[0]},{TradeUi.BUYER_TRADE_REGION[2] - 1}] "
            f"Y[{TradeUi.BUYER_TRADE_REGION[1]},{TradeUi.BUYER_TRADE_REGION[3] - 1}]，"
            f"统一拖拽范围=我方中心区域 "
            f"X[{TradeUi.MY_TRADE_DROP_REGION[0]},{TradeUi.MY_TRADE_DROP_REGION[2] - 1}] "
            f"Y[{TradeUi.MY_TRADE_DROP_REGION[1]},{TradeUi.MY_TRADE_DROP_REGION[3] - 1}]",
            flush=True,
        )
        for index, transfer in enumerate(transfers):
            destination = random_region_point(
                TradeUi.MY_TRADE_DROP_REGION,
                navigator.random_uniform,
            )
            print(
                f"[Lineage][交易界面] 准备放入第 {index + 1}/{len(transfers)} 项 "
                f"{transfer.label}；我方中心区域随机目标="
                f"({destination[0]},{destination[1]})，由游戏自动排序",
                flush=True,
            )
            navigator.drag(transfer.source, destination)
            navigator.wait_after_step(
                f"拖入交易物品 {transfer.label}",
                profile="item_drag",
            )
            navigator.type_text(str(transfer.quantity))
            navigator.press_key("ENTER")
            navigator.wait_after_step(
                f"输入 {transfer.label} 数量 {transfer.quantity} 并确认",
                profile="input",
            )

        confirm = navigator.wait_for_step(
            "等待交易确认按钮可用",
            lambda: navigator.vision.find(
                TradeUi.CONFIRM_BUTTON_TEMPLATE,
                TradeUi.TRADE_ACTION_REGION,
                threshold=0.90,
            ),
            profile="panel",
        )
        if confirm is None:
            raise NavigationError("未找到交易确认按钮")
        navigator.click(confirm)

        final_prompt = navigator.wait_for_step(
            "提交交易内容后等待最终确认提示",
            lambda: navigator.vision.find(
                TradeUi.FINAL_CONFIRM_TEMPLATE, Ui.FULL_CLIENT, threshold=0.90
            ),
            profile="screen",
            fixed_wait=1.0,
        )
        if final_prompt is None:
            return self._result(
                False,
                "verification_failed",
                "FINAL_CONFIRMATION_NOT_FOUND",
                "未识别到最终交易确认提示",
            )
        if self._trade_screenshot_callback is None:
            navigator.click_region(TradeUi.FINAL_REJECT_REGION)
            navigator.wait_after_step("拒绝未留存截图的最终交易", profile="panel")
            return self._result(
                False,
                "failed",
                "TRADE_SCREENSHOT_CHANNEL_MISSING",
                "最终确认前未配置交易截图保存通道，已拒绝最终交易",
            )
        trade_screenshot = navigator.vision.capture_data_url(Ui.FULL_CLIENT)
        if not self._trade_screenshot_callback(trade_screenshot):
            navigator.click_region(TradeUi.FINAL_REJECT_REGION)
            navigator.wait_after_step("拒绝截图保存失败的最终交易", profile="panel")
            return self._result(
                False,
                "failed",
                "TRADE_SCREENSHOT_SAVE_FAILED",
                "最终确认前交易截图未保存到服务器，已拒绝最终交易",
            )
        navigator.click_region(TradeUi.FINAL_ACCEPT_REGION)

        self._emit("verifying", "交易确认已提交，正在验证结果")
        if not self._wait_for_trade_closed(navigator, timeout=12):
            return self._result(
                False,
                "verification_failed",
                "TRADE_RESULT_UNCERTAIN",
                "未获得高置信的交易完成证据",
            )
        return self._result(True, "wait_web_confirm", "", "游戏交易已完成，等待网站确认")

    def _wait_for_expected_buyer(
        self,
        navigator,
        expected_buyer: str,
        timeout: float,
    ) -> Optional[str]:
        """先确认交易申请弹窗，再 OCR 买家名并按置信度决策。"""
        started = time.monotonic()
        deadline = started + timeout
        last_name = ""
        stable_frames = 0
        rejected_name = ""
        last_poll_phase = ""
        while True:
            now = time.monotonic()
            if now >= deadline:
                break
            poll_phase, poll_interval = buyer_poll_schedule(now - started)
            if poll_phase != last_poll_phase:
                print(
                    f"[Lineage][等待买家] 进入{poll_phase}阶段，"
                    f"已等待={now - started:.1f}s，检测间隔={poll_interval:g}s",
                    flush=True,
                )
                last_poll_phase = poll_phase
            navigator._raise_if_cancelled()
            request_marker = navigator.vision.find(
                TradeUi.REQUEST_TEMPLATE,
                TradeUi.REQUEST_TEMPLATE_REGION,
                threshold=0.86,
            )
            if request_marker is None:
                last_name = ""
                stable_frames = 0
                rejected_name = ""
                navigator.sleep(poll_interval)
                continue

            if not last_name:
                request_left, request_top, request_right, request_bottom = (
                    TradeUi.REQUEST_TEMPLATE_REGION
                )
                name_left, name_top, name_right, name_bottom = (
                    TradeUi.CUSTOMER_NAME_REGION
                )
                print(
                    f"[Lineage][交易申请] Yes/No 模板已命中，"
                    f"coordinate=({request_marker[0]},{request_marker[1]})，"
                    f"模板搜索范围=X[{request_left},{request_right - 1}] "
                    f"Y[{request_top},{request_bottom - 1}]，"
                    f"玩家名识别范围=X[{name_left},{name_right - 1}] "
                    f"Y[{name_top},{name_bottom - 1}]",
                    flush=True,
                )

            ocr = navigator.vision.read_text_result(TradeUi.CUSTOMER_NAME_REGION)
            observed = ocr.text.strip()
            normalized = _normalized_customer_name(observed)

            frame_key = normalized or "<unreadable>"
            if frame_key == last_name:
                stable_frames += 1
            else:
                last_name = frame_key
                stable_frames = 1

            if stable_frames >= 2 and frame_key != rejected_name:
                action = buyer_ocr_action(observed, expected_buyer, ocr.confidence)
                if action == "accept":
                    print(
                        f"[Lineage] 高置信交易客户自动通过: observed='{observed}', "
                        f"expected='{expected_buyer}', confidence={ocr.confidence:.1f}"
                    )
                    return observed
                else:
                    approved = self._request_human_buyer_review(
                        navigator, expected_buyer, observed, ocr.confidence, deadline
                    )
                    if approved:
                        return observed or "人工确认的买家"
                    navigator.click_region(TradeUi.REQUEST_REJECT_REGION)
                    rejected_name = frame_key
                    self._emit("waiting_buyer", "人工已拒绝本次申请，继续等待买家")
                    navigator.wait_after_step("拒绝本次买家交易申请", profile="panel")
            navigator.sleep(poll_interval)
        return None

    def _request_human_buyer_review(
        self,
        navigator,
        expected_buyer: str,
        observed_buyer: str,
        confidence: float,
        deadline: float,
    ) -> bool:
        if self._buyer_review_callback is None:
            raise NavigationError("玩家名需要人工判断，但未配置人工审核通道")
        review_id = str(uuid.uuid4())
        screenshot = navigator.vision.capture_data_url(TradeUi.REQUEST_REVIEW_SCREENSHOT_REGION)
        with self._review_condition:
            self._pending_review_id = review_id
            self._review_decision = None
        reason = (
            f"客户名 OCR 置信度 {max(confidence, 0):.1f}"
            if confidence < 90.0
            else "高置信 OCR 玩家名与订单不匹配"
        )
        self._emit("waiting_buyer_review", f"{reason}，等待人工确认")
        try:
            self._buyer_review_callback({
                "review_id": review_id,
                "expected_buyer": expected_buyer,
                "observed_buyer": observed_buyer,
                "ocr_confidence": confidence,
                "screenshot_data_url": screenshot,
            })
            with self._review_condition:
                while self._review_decision is None:
                    if self._cancel_event.is_set():
                        raise NavigationCancelled("交易已取消")
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        return False
                    self._review_condition.wait(timeout=min(0.5, remaining))
                return self._review_decision
        finally:
            with self._review_condition:
                self._pending_review_id = None
                self._review_decision = None

    def _build_transfers(self, order: dict, navigator) -> list[TradeTransfer]:
        asset_type = str(order.get("asset_type") or "").strip().casefold()
        details = list(order.get("details") or [])
        if not details:
            raise NavigationError(f"资产类型 {asset_type or 'unknown'} 没有可交易的物品明细")
        transfers: list[TradeTransfer] = []
        for detail in details:
            item_id = detail.get("item_id")
            label = str(detail.get("item_name") or item_id or "未知物品")
            images = item_recognition_images(detail)
            def locate_source():
                for image in images:
                    source_point = navigator.vision.find_image(
                        image,
                        Ui.INVENTORY_CONTENT_REGION,
                        threshold=0.90,
                    )
                    if source_point is not None:
                        return source_point
                return None

            source = navigator.wait_for_step(
                f"在物品栏识别 {label}",
                locate_source,
                profile="recognition",
            )
            if source is None:
                raise NavigationError(f"物品栏中未识别到物品 {label}")
            quantity_value = (
                order.get("asset_amount")
                if asset_type in {"adena", "gold", "金币", "아데나"}
                else detail.get("quantity")
            )
            quantity = self._positive_quantity(quantity_value, label)
            transfers.append(TradeTransfer(source=source, quantity=quantity, label=label))
        return transfers

    @staticmethod
    def _positive_quantity(value, label: str) -> int:
        try:
            numeric = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise NavigationError(f"{label} 交易数量无效") from exc
        if numeric <= 0 or numeric != numeric.to_integral_value():
            raise NavigationError(f"{label} 交易数量必须是大于 0 的整数")
        return int(numeric)

    def _wait_for_trade_closed(self, navigator, timeout: float) -> bool:
        """连续三帧确认交易窗口和最终提示均消失，且已回到游戏主界面。"""
        stable_frames = 0

        def trade_closed_sample() -> bool:
            nonlocal stable_frames
            if self._cancel_event.is_set():
                raise NavigationCancelled("交易已取消")
            final_prompt = navigator.vision.find(
                TradeUi.FINAL_CONFIRM_TEMPLATE, Ui.FULL_CLIENT, threshold=0.90
            )
            cancel_button = navigator.vision.find(
                TradeUi.CANCEL_BUTTON_TEMPLATE,
                TradeUi.TRADE_ACTION_REGION,
                threshold=0.90,
            )
            if final_prompt is None and cancel_button is None and navigator._is_in_game():
                stable_frames += 1
                if stable_frames >= 3:
                    return True
            else:
                stable_frames = 0
            return False

        result = navigator.wait_for_step(
            "最终确认后验证交易窗口关闭",
            trade_closed_sample,
            profile="final_verify",
            fixed_wait=1.0,
            attempts=3,
            probe_interval=0.5,
        )
        return bool(result)

    def _emit(self, status: str, message: str) -> None:
        self._phase = status
        if self._cancel_event.is_set():
            raise NavigationCancelled("交易已取消")
        print(
            f"[Lineage][流程状态] {status}: {message}",
            flush=True,
        )
        if self._progress is not None:
            self._progress(status, message)

    def _pause(self, navigator, seconds: float) -> None:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if self._cancel_event.is_set():
                raise NavigationCancelled("交易已取消")
            navigator.sleep(min(0.1, max(0.0, deadline - time.monotonic())))

    @staticmethod
    def _result(success: bool, status: str, error_code: str, message: str) -> dict:
        return {
            "success": success,
            "status": status,
            "error_code": error_code,
            "message": message,
        }
