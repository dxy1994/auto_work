package com.auto.trade;

/** 游戏执行器识别到服务器断线弹窗，并准备关闭对应游戏进程。 */
public record GameClientDisconnected(
        int machineId,
        String gameCode,
        String gameName,
        String account,
        Integer gameAccountId,
        Integer processId,
        double confidence,
        String reason) {
}
