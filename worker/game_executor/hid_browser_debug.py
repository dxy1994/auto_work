"""用真实 Wireless HID 验证浏览器、键盘、鼠标轨迹和滚轮。

运行：
    cd worker
    python -m game_executor.hid_browser_debug

脚本启动后会真实接管键鼠，请先保存正在编辑的内容。
"""

from __future__ import annotations

import asyncio
import json
import random
import string
import time
from typing import Callable, Optional

from common import config
from game_executor.executor.hardware.controller import HardwareController
from game_executor.executor.hardware.humanized import HumanizedInputController
from game_executor.hardware_binding import WirelessHidBinding


ScreenBounds = tuple[int, int, int, int]
GOOGLE_ADDRESS = "google.com"


async def resolve_hardware_binding() -> WirelessHidBinding:
    """Resolve this host's assigned HID without replacing its Worker session."""
    import websockets

    info = config.get_machine_info()
    async with websockets.connect(config.BACKEND_WS_URL, max_size=None) as ws:
        await ws.send(json.dumps({
            "type": "hardware_binding_request",
            "mac": info["mac"],
        }))
        raw = await asyncio.wait_for(ws.recv(), timeout=10.0)
    message = json.loads(raw)
    if message.get("type") != "hardware_binding":
        raise RuntimeError("总控未返回键鼠绑定")
    payload = message.get("wireless_hid")
    if payload is None:
        raise RuntimeError(message.get("hardware_error") or "当前机器尚未绑定键鼠设备")
    return WirelessHidBinding.from_payload(payload)


def primary_screen_bounds() -> ScreenBounds:
    """Return the primary Windows screen bounds in absolute pixels."""
    try:
        import ctypes

        user32 = ctypes.windll.user32
        width = int(user32.GetSystemMetrics(0))
        height = int(user32.GetSystemMetrics(1))
        if width > 0 and height > 0:
            return 0, 0, width - 1, height - 1
    except (AttributeError, OSError):
        pass
    return 0, 0, 1919, 1079


def random_search_text(random_source: random.Random) -> str:
    length = random_source.randint(8, 14)
    alphabet = string.ascii_lowercase + string.digits
    return "".join(random_source.choice(alphabet) for _ in range(length))


def run_debug_sequence(
    input_controller: HumanizedInputController,
    hardware: HardwareController,
    *,
    random_source: Optional[random.Random] = None,
    sleep: Callable[[float], None] = time.sleep,
    screen_bounds: Optional[ScreenBounds] = None,
    emit: Callable[[str], None] = print,
) -> dict[str, object]:
    """Run the synchronous HID browser scenario and return its random choices."""
    rng = random_source or random.Random()
    bounds = screen_bounds or primary_screen_bounds()
    left, top, right, bottom = bounds
    width = max(1, right - left + 1)
    height = max(1, bottom - top + 1)
    search_box = (
        left + round(width * 0.50),
        top + round(height * 0.45),
    )
    random_target = (
        rng.randint(left + round(width * 0.15), left + round(width * 0.85)),
        rng.randint(top + round(height * 0.25), top + round(height * 0.75)),
    )
    query = random_search_text(rng)
    scroll_steps = -rng.randint(6, 12)

    _run_step(
        "打开 Windows 运行窗口",
        lambda: input_controller.press_combo(["win", "r"]),
        hardware,
        emit,
    )
    sleep(rng.uniform(0.8, 1.3))
    _run_step(
        f"输入地址 {GOOGLE_ADDRESS}",
        lambda: input_controller.type_text(GOOGLE_ADDRESS),
        hardware,
        emit,
    )
    _run_step(
        "打开默认浏览器",
        lambda: input_controller.press_key("ENTER"),
        hardware,
        emit,
    )
    sleep(rng.uniform(7.0, 10.0))

    _run_step(
        "点击 Google 搜索框",
        lambda: input_controller.click_at(
            *search_box,
            radius_x=max(6, round(width * 0.01)),
            radius_y=max(3, round(height * 0.005)),
            bounds=bounds,
        ),
        hardware,
        emit,
    )
    _run_step(
        f"输入随机搜索词 {query}",
        lambda: input_controller.type_text(query),
        hardware,
        emit,
    )
    _run_step(
        "提交 Google 搜索",
        lambda: input_controller.press_key("ENTER"),
        hardware,
        emit,
    )
    sleep(rng.uniform(7.0, 10.0))

    _run_step(
        f"移动鼠标到随机位置 {random_target}",
        lambda: input_controller.move_to(
            *random_target,
            radius_x=8,
            radius_y=8,
            bounds=bounds,
        ),
        hardware,
        emit,
    )
    sleep(rng.uniform(0.5, 1.0))
    _run_step(
        f"向下滚动 {abs(scroll_steps)} 格",
        lambda: input_controller.scroll(scroll_steps),
        hardware,
        emit,
    )

    return {
        "query": query,
        "search_box": search_box,
        "random_target": random_target,
        "scroll_steps": scroll_steps,
    }


def _run_step(
    label: str,
    action: Callable[[], bool],
    hardware: HardwareController,
    emit: Callable[[str], None],
) -> None:
    if action() is False:
        feedback = hardware.last_feedback or {}
        raise RuntimeError(
            f"{label}失败: {feedback.get('error') or 'hardware returned false'}"
        )
    emit(
        "[HID-DEBUG] "
        + json.dumps(
            {
                "step": label,
                "status": "completed",
                "feedback": hardware.last_feedback,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )


def main() -> int:
    try:
        binding = asyncio.run(resolve_hardware_binding())
    except Exception as exc:
        print(f"[HID-DEBUG] 无法读取本机键鼠绑定: {exc}", flush=True)
        return 1
    hardware = HardwareController(
        binding.host,
        binding.port,
        expected_device_id=binding.device_id,
    )
    print(
        "[HID-DEBUG] 3 秒后开始真实键鼠测试，请保存当前工作并停止触碰键鼠。",
        flush=True,
    )
    for remaining in range(3, 0, -1):
        print(f"[HID-DEBUG] {remaining}...", flush=True)
        time.sleep(1.0)

    if not hardware.connect():
        print(
            "[HID-DEBUG] 连接 Wireless HID 失败: "
            + json.dumps(hardware.last_feedback, ensure_ascii=False),
            flush=True,
        )
        return 1

    try:
        input_controller = HumanizedInputController(hardware)
        result = run_debug_sequence(input_controller, hardware)
        print(
            "[HID-DEBUG] 测试完成 "
            + json.dumps(result, ensure_ascii=False, separators=(",", ":")),
            flush=True,
        )
        return 0
    except Exception as exc:
        print(f"[HID-DEBUG] 测试失败: {exc}", flush=True)
        return 1
    finally:
        hardware.disconnect()


if __name__ == "__main__":
    raise SystemExit(main())
