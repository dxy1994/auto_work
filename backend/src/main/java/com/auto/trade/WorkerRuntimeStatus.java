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

    public boolean isGameExecutor() {
        return isGameExecutorRole(role);
    }

    public static boolean isGameExecutorRole(String role) {
        return "game_executor".equals(role) || "trader".equals(role);
    }

    public boolean isMonitor() {
        return "monitor".equals(role);
    }
}
