"""使用正式交易执行器运行测试订单，但阻断所有键鼠指令。

窗口发现、OCR、模板匹配、截图、等待和状态编排均使用正式实现；
唯一替换的是 ESP32 键鼠控制器。日志控制器会记录原本要发送的动作并返回成功，
但不会进行网络请求，也不会移动、点击鼠标或发送键盘按键。

运行：
    python -m game_executor.dry_run_trade
    python -m game_executor.dry_run_trade --amount 2500000 --buyer DryRunBuyer
"""

import argparse
import asyncio
import base64
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from common.context import AppContext
from game_executor.executor.lineage_classic import LineageClassicExecutor
from game_executor.executor.hardware.log_only import LogOnlyHardwareController
from game_executor.executor.registry import ExecutorRegistry
from game_executor.gate import TradeTaskGate
from game_executor.status import RuntimeStatus
import game_executor.main as executor_main


class LocalLogReporter:
    """在本地打印 Worker 上报事件；交易截图保存到系统临时目录。"""

    def report_trade_offer_decision(self, assignment_id, accepted, reason=""):
        self._log(
            "offer_decision",
            assignment_id=assignment_id,
            accepted=bool(accepted),
            reason=reason or "accepted",
        )

    def report_trade_status(
        self, assignment_id, status, message="", error_code=""
    ):
        self._log(
            "trade_status",
            assignment_id=assignment_id,
            status=status,
            message=message,
            error_code=error_code,
        )

    def report_trade_buyer_review(self, assignment_id, review):
        self._log("buyer_review_required", assignment_id=assignment_id, review=review)

    def save_trade_game_screenshot(self, assignment_id, screenshot_data_url):
        try:
            header, payload = screenshot_data_url.split(",", 1)
            suffix = ".jpg" if "jpeg" in header.casefold() else ".png"
            output_dir = Path(tempfile.gettempdir()) / "auto-work-trade-dry-run"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"{assignment_id}{suffix}"
            output_path.write_bytes(base64.b64decode(payload))
            self._log(
                "trade_screenshot_saved",
                assignment_id=assignment_id,
                path=str(output_path),
            )
            return True
        except Exception as exc:
            self._log(
                "trade_screenshot_failed",
                assignment_id=assignment_id,
                error=str(exc),
            )
            return False

    @staticmethod
    def _log(event, **values):
        print(
            "[TRADE-DRY-RUN] "
            + json.dumps(
                {"event": event, **values},
                ensure_ascii=False,
                separators=(",", ":"),
                default=str,
            )
        )


def build_test_order(amount, buyer):
    now = datetime.now(timezone.utc)
    suffix = now.strftime("%Y%m%d%H%M%S")
    return {
        "order_id": f"TEST-{suffix}",
        "game_code": "lineage_classic",
        "game_id": 1,
        "game_account_id": 1,
        "trade_timeout_seconds": 30,
        "region_id": 999001,
        "region_name": "测试大区",
        "region_code": "DRY_RUN_REGION",
        "region_sort_order": 1,
        "region_select_x": 310,
        "region_select_y": 154,
        "buyer_character": buyer,
        "asset_type": "adena",
        "asset_amount": amount,
        "details": [
            {
                "item_id": 999001,
                "item_name": "Adena（测试）",
                "quantity": amount,
                "recognition_image_unselected_url": (
                    "data:image/png;base64,"
                    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwC"
                    "AAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
                ),
                "recognition_image_selected_url": (
                    "data:image/png;base64,"
                    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwC"
                    "AAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
                ),
            }
        ],
        "item_positions": [],
    }


async def run_dry_trade(order):
    assignment_id = f"dry-run-{order['order_id']}"
    execution_token = f"dry-run-token-{order['order_id']}"

    reporter = LocalLogReporter()
    hardware = LogOnlyHardwareController()
    registry = ExecutorRegistry()
    context = AppContext(asyncio.get_running_loop())
    context.reporter = reporter
    context.runtime_status = RuntimeStatus()
    context.trade_task_gate = TradeTaskGate()
    registry.register(LineageClassicExecutor(hardware, context.runtime_status))

    reporter._log(
        "test_order",
        order=order,
        safety="窗口/OCR/截图正常；ESP32 键鼠指令强制阻断",
    )
    original_registry = executor_main.EXECUTOR_REGISTRY
    executor_main.EXECUTOR_REGISTRY = registry
    try:
        await executor_main._dispatch_message(
            {
                "type": "trade_offer",
                "assignment_id": assignment_id,
                "execution_token": execution_token,
                "order": order,
            },
            context,
        )
        await executor_main._dispatch_message(
            {
                "type": "trade_start",
                "assignment_id": assignment_id,
                "execution_token": execution_token,
            },
            context,
        )
        active = context.active_trade(assignment_id)
        if active is None:
            raise RuntimeError("测试交易任务未启动")
        await active["task"]
    finally:
        executor_main.EXECUTOR_REGISTRY = original_registry

    reporter._log(
        "dry_run_finished",
        gate=context.trade_task_gate.snapshot(),
        runtime=context.runtime_status.snapshot(),
        planned_hid_actions=hardware.planned_actions,
        sent_hid_actions=0,
    )


def main():
    parser = argparse.ArgumentParser(
        description="正式交易流程干跑（仅阻断 ESP32 键鼠指令）"
    )
    parser.add_argument("--amount", type=int, default=1_000_000, help="测试 Adena 数量")
    parser.add_argument("--buyer", default="DryRunBuyer", help="测试买家角色名")
    args = parser.parse_args()
    if args.amount <= 0:
        parser.error("--amount 必须大于 0")
    asyncio.run(run_dry_trade(build_test_order(args.amount, args.buyer)))


if __name__ == "__main__":
    main()
