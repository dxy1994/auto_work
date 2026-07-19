package com.auto.trade;

/** Worker 随心跳上报的游戏客户端与交易执行器状态。 */
public record WorkerRuntimeStatus(
        String role,
        Integer gameId,
        Integer gameAccountId,
        Integer regionId,
        String clientStatus,
        String characterName,
        String executorStatus,
        String currentAssignmentId,
        String uiHealth) {

    public boolean isTrader() {
        return "trader".equals(role);
    }

    public boolean isMonitor() {
        return "monitor".equals(role);
    }
}
