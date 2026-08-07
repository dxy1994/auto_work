"""天堂经典版订单执行策略。"""

DEFAULT_TRADE_TIMEOUT_SECONDS = 600
MIN_TRADE_TIMEOUT_SECONDS = 30
MAX_TRADE_TIMEOUT_SECONDS = 7200
EXECUTION_WATCHDOG_GRACE_SECONDS = 600

BUYER_POLL_INITIAL_PHASE_SECONDS = 60
BUYER_POLL_FREQUENT_PHASE_END_SECONDS = 420
BUYER_POLL_INITIAL_INTERVAL_SECONDS = 5.0
BUYER_POLL_FREQUENT_INTERVAL_SECONDS = 2.0
BUYER_POLL_LATE_INTERVAL_SECONDS = 5.0
BUYER_POLL_POST_REJECT_INTERVAL_SECONDS = 0.5
BUYER_POLL_POST_REJECT_FAST_WINDOW_SECONDS = 15.0


def trade_timeout_seconds(order: dict) -> int:
    """读取后台固化到订单消息中的交易申请等待时长。"""
    try:
        value = int(order.get("trade_timeout_seconds", DEFAULT_TRADE_TIMEOUT_SECONDS))
    except (TypeError, ValueError):
        value = DEFAULT_TRADE_TIMEOUT_SECONDS
    return min(MAX_TRADE_TIMEOUT_SECONDS, max(MIN_TRADE_TIMEOUT_SECONDS, value))


def buyer_poll_schedule(elapsed_seconds: float) -> tuple[str, float]:
    """按已等待时长返回玩家交易申请检测阶段和间隔。"""
    elapsed = max(0.0, float(elapsed_seconds))
    if elapsed < BUYER_POLL_INITIAL_PHASE_SECONDS:
        return "初始低频", BUYER_POLL_INITIAL_INTERVAL_SECONDS
    if elapsed < BUYER_POLL_FREQUENT_PHASE_END_SECONDS:
        return "中段高频", BUYER_POLL_FREQUENT_INTERVAL_SECONDS
    return "后段低频", BUYER_POLL_LATE_INTERVAL_SECONDS


def execution_timeout_seconds(order: dict) -> int:
    """整个执行的硬超时：买家等待时间 + 切区/交易/验证宽限。"""
    return trade_timeout_seconds(order) + EXECUTION_WATCHDOG_GRACE_SECONDS
