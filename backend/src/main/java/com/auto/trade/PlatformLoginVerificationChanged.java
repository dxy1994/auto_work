package com.auto.trade;

/** 平台账号登录验证码变为待处理或已经恢复。 */
public record PlatformLoginVerificationChanged(
        int machineId,
        int accountId,
        String platform,
        String status,
        String reason) {
}
