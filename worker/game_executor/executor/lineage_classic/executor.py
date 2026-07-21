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
from game_executor.executor.lineage_classic.policy import trade_timeout_seconds


class TradeUi:
    # 整图只辅助判断弹窗是否存在，不用于客户身份判断。
    REQUEST_TEMPLATE = "交易弹窗提醒.png"
    CONFIRM_BUTTON_TEMPLATE = "交易确认按钮.png"
    CANCEL_BUTTON_TEMPLATE = "交易取消按钮.png"
    FINAL_CONFIRM_TEMPLATE = "最终确认交易判断.png"
    CUSTOMER_NAME_REGION = (144, 516, 241, 538)
    REQUEST_ACCEPT_REGION = (528, 547, 547, 556)
    REQUEST_REJECT_REGION = (561, 547, 575, 556)
    BOTH_TRADE_REGION = (9, 11, 215, 355)
    MY_TRADE_REGION = (26, 45, 180, 156)
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

    def __init__(self, hw, runtime_status=None):
        super().__init__(hw)
        self._runtime_status = runtime_status
        self._cancel_event = threading.Event()
        self._progress: Optional[Callable[[str, str], None]] = None
        self._buyer_review_callback: Optional[Callable[[dict], None]] = None
        self._trade_screenshot_callback: Optional[Callable[[str], bool]] = None
        self._review_condition = threading.Condition()
        self._pending_review_id: Optional[str] = None
        self._review_decision: Optional[bool] = None
        self._phase = "idle"

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

    def probe_runtime(self) -> bool:
        """启动和空闲期检查唯一的天堂窗口，不执行键鼠操作。"""
        try:
            window = ClientWindow.find()
            window.validate_size()
            navigator = LineageSessionNavigator(
                self._hw, window, TemplateVision(window), runtime_status=self._runtime_status
            )
            ready = navigator._is_in_game()
        except NavigationError as exc:
            print(f"[Lineage] 运行态检查失败: {exc}")
            ready = False
        if self._runtime_status is not None:
            self._runtime_status.update(
                client_status="logged_in" if ready else "not_ready",
                ui_health="ready" if ready else "unhealthy",
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
        navigator.click(region_center(TradeUi.REQUEST_ACCEPT_REGION))
        self._pause(navigator, 0.8)
        trade_cancel = navigator._wait_for(
            lambda: navigator.vision.find(
                TradeUi.CANCEL_BUTTON_TEMPLATE, TradeUi.BOTH_TRADE_REGION, threshold=0.90
            ),
            timeout=5,
            interval=0.25,
        )
        if trade_cancel is None:
            raise NavigationError("接受申请后未识别到交易界面")

        destination = region_center(TradeUi.MY_TRADE_REGION)
        for transfer in transfers:
            navigator.drag(transfer.source, destination)
            self._pause(navigator, 0.25)
            if (self._hw.key_type(str(transfer.quantity)) is False
                    or self._hw.key_press("ENTER") is False):
                raise NavigationError(f"硬件输入 {transfer.label} 数量失败")
            self._pause(navigator, 0.45)

        confirm = navigator._wait_for(
            lambda: navigator.vision.find(
                TradeUi.CONFIRM_BUTTON_TEMPLATE, TradeUi.BOTH_TRADE_REGION, threshold=0.90
            ),
            timeout=5,
            interval=0.25,
        )
        if confirm is None:
            raise NavigationError("未找到交易确认按钮")
        navigator.click(confirm)
        self._pause(navigator, 1.0)

        final_prompt = navigator._wait_for(
            lambda: navigator.vision.find(
                TradeUi.FINAL_CONFIRM_TEMPLATE, Ui.FULL_CLIENT, threshold=0.90
            ),
            timeout=8,
            interval=0.25,
        )
        if final_prompt is None:
            return self._result(
                False,
                "verification_failed",
                "FINAL_CONFIRMATION_NOT_FOUND",
                "未识别到最终交易确认提示",
            )
        if self._trade_screenshot_callback is None:
            navigator.click(region_center(TradeUi.FINAL_REJECT_REGION))
            return self._result(
                False,
                "failed",
                "TRADE_SCREENSHOT_CHANNEL_MISSING",
                "最终确认前未配置交易截图保存通道，已拒绝最终交易",
            )
        trade_screenshot = navigator.vision.capture_data_url(Ui.FULL_CLIENT)
        if not self._trade_screenshot_callback(trade_screenshot):
            navigator.click(region_center(TradeUi.FINAL_REJECT_REGION))
            return self._result(
                False,
                "failed",
                "TRADE_SCREENSHOT_SAVE_FAILED",
                "最终确认前交易截图未保存到服务器，已拒绝最终交易",
            )
        navigator.click(region_center(TradeUi.FINAL_ACCEPT_REGION))

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
        """90 分及以上自动按前缀决策；低置信结果必须由前端人工决策。"""
        deadline = time.monotonic() + timeout
        last_name = ""
        stable_frames = 0
        rejected_name = ""
        while time.monotonic() < deadline:
            navigator._raise_if_cancelled()
            ocr = navigator.vision.read_text_result(TradeUi.CUSTOMER_NAME_REGION)
            observed = ocr.text.strip()
            normalized = _normalized_customer_name(observed)
            request_visible = bool(normalized)
            if not request_visible:
                request_visible = navigator.vision.find(
                    TradeUi.REQUEST_TEMPLATE, Ui.FULL_CLIENT, threshold=0.72
                ) is not None
            if not request_visible:
                last_name = ""
                stable_frames = 0
                rejected_name = ""
                navigator.sleep(0.35)
                continue

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
                    navigator.click(region_center(TradeUi.REQUEST_REJECT_REGION))
                    rejected_name = frame_key
                    self._emit("waiting_buyer", "人工已拒绝本次申请，继续等待买家")
                    self._pause(navigator, 0.8)
            navigator.sleep(0.35)
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
            source = None
            for image in images:
                source = navigator.vision.find_image(
                    image, Ui.INVENTORY_REGION, threshold=0.90
                )
                if source is not None:
                    break
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
        deadline = time.monotonic() + timeout
        stable_frames = 0
        while time.monotonic() < deadline:
            if self._cancel_event.is_set():
                raise NavigationCancelled("交易已取消")
            final_prompt = navigator.vision.find(
                TradeUi.FINAL_CONFIRM_TEMPLATE, Ui.FULL_CLIENT, threshold=0.90
            )
            cancel_button = navigator.vision.find(
                TradeUi.CANCEL_BUTTON_TEMPLATE, TradeUi.BOTH_TRADE_REGION, threshold=0.90
            )
            if final_prompt is None and cancel_button is None and navigator._is_in_game():
                stable_frames += 1
                if stable_frames >= 3:
                    return True
            else:
                stable_frames = 0
            navigator.sleep(0.5)
        return False

    def _emit(self, status: str, message: str) -> None:
        self._phase = status
        if self._cancel_event.is_set():
            raise NavigationCancelled("交易已取消")
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
