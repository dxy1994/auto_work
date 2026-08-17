package com.auto.trade;

import java.time.Instant;
import java.util.Map;

/** 总控发给 Worker 的临时指派；执行令牌不落明文数据库。 */
public record TradeOffer(
        String assignmentId,
        int orderId,
        int machineId,
        int gameAccountId,
        String executionToken,
        Instant leaseExpiresAt,
        Map<String, Object> orderPayload) {
}
