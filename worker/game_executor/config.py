"""游戏执行主机专用配置。"""

import os


ESP32_HOST = os.getenv("ESP32_HOST", "192.168.1.100")


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().casefold() in {"1", "true", "yes", "on"}


# 人工操作测试模式：仍接收并执行总控真实订单，识别和终态上报完全真实，
# 但所有 HID 动作只输出待人工执行的日志。旧变量仅作为安全兼容，避免升级后误发 HID。
MANUAL_ACTIONS = _env_flag(
    "GAME_EXECUTOR_MANUAL_ACTIONS",
    _env_flag("GAME_EXECUTOR_DRY_RUN", False),
)

try:
    MANUAL_ACTION_WAIT_SECONDS = max(
        0.0, float(os.getenv("GAME_EXECUTOR_MANUAL_ACTION_WAIT_SECONDS", "5"))
    )
except ValueError:
    MANUAL_ACTION_WAIT_SECONDS = 5.0
