package com.auto.trade;

import java.time.Instant;

/** 总控调度器用于评估的一台机器及其绑定游戏账号快照。 */
public record TradeCandidate(
        int machineId,
        int gameAccountId,
        int gameId,
        int regionId,
        int priority,
        boolean machineOnline,
        boolean accountIdle,
        boolean runtimeMatchesAccount,
        String clientStatus,
        String executorStatus,
        String uiHealth,
        Instant lastUsedAt) {
}
