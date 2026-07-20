"""天堂经典版订单执行策略。"""

DEFAULT_TRADE_TIMEOUT_SECONDS = 300
MIN_TRADE_TIMEOUT_SECONDS = 30
MAX_TRADE_TIMEOUT_SECONDS = 7200
EXECUTION_WATCHDOG_GRACE_SECONDS = 180


def trade_timeout_seconds(order: dict) -> int:
    """读取后台固化到订单消息中的交易申请等待时长。"""
    try:
        value = int(order.get("trade_timeout_seconds", DEFAULT_TRADE_TIMEOUT_SECONDS))
    except (TypeError, ValueError):
        value = DEFAULT_TRADE_TIMEOUT_SECONDS
    return min(MAX_TRADE_TIMEOUT_SECONDS, max(MIN_TRADE_TIMEOUT_SECONDS, value))


def execution_timeout_seconds(order: dict) -> int:
    """整个执行的硬超时：买家等待时间 + 切区/交易/验证宽限。"""
    return trade_timeout_seconds(order) + EXECUTION_WATCHDOG_GRACE_SECONDS
