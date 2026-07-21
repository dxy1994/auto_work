"""游戏执行主机专用配置。"""

import os


ESP32_HOST = os.getenv("ESP32_HOST", "192.168.1.100")


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().casefold() in {"1", "true", "yes", "on"}


# true 时仍接收总控真实订单，但所有 HID 动作只写日志。
DRY_RUN = _env_flag("GAME_EXECUTOR_DRY_RUN", False)
