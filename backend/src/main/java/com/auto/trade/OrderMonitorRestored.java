package com.auto.trade;

/** Worker 已通过任务状态或心跳确认指定账号的订单监控正在运行。 */
public record OrderMonitorRestored(int machineId, int accountId, String taskId) {
}
