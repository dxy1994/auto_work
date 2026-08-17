package com.auto.trade;

/** Worker 重新连接或恢复心跳后，机器重新进入在线状态。 */
public record MachineSessionRestored(int machineId) {
}
