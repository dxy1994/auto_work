package com.auto.trade;

/** Worker 会话丢失或被新连接替换。 */
public record MachineSessionLost(int machineId, String reason) {
}
