package com.auto.trade;

/** 为订单错误补充统一的“原因 + 解决方案”，避免只记录无法执行的异常文本。 */
public final class TradeErrorGuidance {

    private static final int MAX_LENGTH = 500;

    private TradeErrorGuidance() {
    }

    public static String ensureGuidance(String errorCode, String message) {
        String value = message == null || message.isBlank() ? "未提供具体异常信息" : message.trim();
        if (value.contains("解决方案：")) {
            return limit(value);
        }
        String solution = switch (errorCode == null ? "" : errorCode) {
            case "GREETING_FAILED", "GREETING_EXECUTION_FAILED" ->
                    "检查监控端是否在线、浏览器是否保持登录，并确认招呼脚本的页面元素配置有效后重试";
            case "GREETING_RESULT_PROCESSING_ERROR" ->
                    "查看同一 order_id 的后端异常堆栈，确认数据库字段与最新迁移一致后重试";
            case "TRADE_DISPATCH_FAILED" ->
                    "检查游戏执行机器、游戏账号、大区和库存关联是否完整且处于可用状态后重新指派";
            case "START_DISPATCH_FAILED" ->
                    "确认游戏执行端在线且未被其他订单占用，然后重新发起交易";
            case "TRADE_REQUEST_TIMEOUT", "EXECUTION_WATCHDOG_TIMEOUT" ->
                    "检查执行端网络和游戏状态，并人工确认本次交易结果后决定重试或完成";
            case "FINAL_CONFIRMATION_NOT_FOUND" ->
                    "系统未能识别最终确认提示，无法据此判断当前界面；请人工核对游戏和平台的实际交易结果，再选择“复核为已完成”或“复核为已取消”";
            case "TRADE_RESULT_UNCERTAIN" ->
                    "在游戏和平台核对实际交易结果，完成人工复核后再更新订单状态";
            case "TRADE_RETRYABLE_FAILURE" ->
                    "根据执行端日志修正临时问题，并在确认游戏界面恢复后重试";
            case "WEBSITE_DELIVERY_DISPATCH_FAILED" ->
                    "检查订单来源账号的监控机器、RustFS 截图路径和平台聊天/交付配置后重新处理";
            case "WEBSITE_DELIVERY_CONFIRM_FAILED" ->
                    "检查平台账号登录状态、聊天图片上传结果和订单详情页交付按钮后人工确认或重试";
            default -> "根据错误码查看对应服务日志，修正配置或运行环境后重试；无法确认结果时转人工处理";
        };
        return limit("原因：" + value + "。解决方案：" + solution + "。");
    }

    private static String limit(String value) {
        return value.length() <= MAX_LENGTH ? value : value.substring(0, MAX_LENGTH);
    }
}
