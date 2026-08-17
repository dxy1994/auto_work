package com.auto.trade;

/** 订单监控任务在未收到用户主动终止时结束。 */
public record OrderMonitorStopped(int machineId, int accountId, String taskId,
                                  String status, String message) {
}
