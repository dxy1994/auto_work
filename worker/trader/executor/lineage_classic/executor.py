"""Lineage Classic 正式交易执行器。"""

from __future__ import annotations

import asyncio
import threading
import time
from typing import Callable, Optional

from trader.executor.base import BaseGameExecutor
from trader.executor.lineage_classic.navigation import (
    ClientWindow,
    NavigationCancelled,
    NavigationError,
    LineageSessionNavigator,
    TemplateVision,
    Ui,
    build_navigator,
)
from trader.executor.lineage_classic.policy import trade_timeout_seconds


class TradeUi:
    REQUEST_TEMPLATE = "交易弹窗提醒.png"
    CONFIRM_BUTTON_TEMPLATE = "交易确认按钮.png"
    CANCEL_BUTTON_TEMPLATE = "交易取消按钮.png"
    FINAL_CONFIRM_TEMPLATE = "最终确认交易判断.png"
    REQUEST_REGION = Ui.FULL_CLIENT
    REQUEST_YES_OFFSET = (137, 12)
    GOLD_ICON = (512, 460)
    GOLD_DROP_SLOT = (760, 300)
    AMOUNT_INPUT = (760, 360)


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
        self._phase = "idle"

    def set_progress_callback(self, callback: Optional[Callable[[str, str], None]]) -> None:
        self._progress = callback

    def cancel(self):
        self._cancel_event.set()

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
        request = navigator._wait_for(
            lambda: navigator.vision.find(
                TradeUi.REQUEST_TEMPLATE, TradeUi.REQUEST_REGION, threshold=0.90
            ),
            timeout=trade_timeout_seconds(order),
            interval=0.5,
        )
        if request is None:
            return self._result(
                False,
                "timed_out",
                "TRADE_REQUEST_TIMEOUT",
                "等待买家交易申请超时",
            )

        try:
            amount = int(order.get("asset_amount"))
        except (TypeError, ValueError):
            return self._result(False, "failed", "INVALID_ASSET_AMOUNT", "交易数量无效")
        if amount <= 0:
            return self._result(False, "failed", "INVALID_ASSET_AMOUNT", "交易数量必须大于 0")

        asset_type = str(order.get("asset_type") or "").strip().casefold()
        if asset_type not in {"adena", "gold", "金币", "아데나"}:
            return self._result(
                False, "failed", "UNSUPPORTED_ASSET_TYPE", f"不支持的资产类型: {asset_type}"
            )

        self._emit("trading", "已收到交易申请，正在放入金币并确认")
        navigator.click((request[0] + TradeUi.REQUEST_YES_OFFSET[0], request[1] + TradeUi.REQUEST_YES_OFFSET[1]))
        self._pause(navigator, 0.8)
        trade_cancel = navigator._wait_for(
            lambda: navigator.vision.find(
                TradeUi.CANCEL_BUTTON_TEMPLATE, Ui.FULL_CLIENT, threshold=0.90
            ),
            timeout=5,
            interval=0.25,
        )
        if trade_cancel is None:
            raise NavigationError("接受申请后未识别到交易界面")
        navigator.drag(TradeUi.GOLD_ICON, TradeUi.GOLD_DROP_SLOT)
        navigator.click(TradeUi.AMOUNT_INPUT)
        if self._hw.key_type(str(amount)) is False or self._hw.key_press("ENTER") is False:
            raise NavigationError("硬件输入交易金额失败")
        confirm = navigator._wait_for(
            lambda: navigator.vision.find(
                TradeUi.CONFIRM_BUTTON_TEMPLATE, Ui.FULL_CLIENT, threshold=0.90
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
        final_confirm = navigator._wait_for(
            lambda: navigator.vision.find(
                TradeUi.CONFIRM_BUTTON_TEMPLATE, Ui.FULL_CLIENT, threshold=0.90
            ),
            timeout=5,
            interval=0.25,
        )
        if final_confirm is None:
            return self._result(
                False,
                "verification_failed",
                "FINAL_CONFIRM_BUTTON_NOT_FOUND",
                "最终确认页未找到确认按钮",
            )
        navigator.click(final_confirm)

        self._emit("verifying", "交易确认已提交，正在验证结果")
        if not self._wait_for_trade_closed(navigator, timeout=12):
            return self._result(
                False,
                "verification_failed",
                "TRADE_RESULT_UNCERTAIN",
                "未获得高置信的交易完成证据",
            )
        return self._result(True, "completed", "", "交易已完成并验证")

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
                TradeUi.CANCEL_BUTTON_TEMPLATE, Ui.FULL_CLIENT, threshold=0.90
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
