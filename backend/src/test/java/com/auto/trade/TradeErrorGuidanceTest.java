package com.auto.trade;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class TradeErrorGuidanceTest {

    @Test
    void addsReasonAndActionableSolution() {
        String result = TradeErrorGuidance.ensureGuidance(
                "START_DISPATCH_FAILED", "发送交易启动指令失败");

        assertTrue(result.startsWith("原因：发送交易启动指令失败"));
        assertTrue(result.contains("解决方案："));
        assertTrue(result.contains("游戏执行端在线"));
    }

    @Test
    void preservesMessagesThatAlreadyContainGuidance() {
        String message = "原因：标题格式错误。解决方案：改为 %物品名%。";
        assertEquals(message, TradeErrorGuidance.ensureGuidance("ITEM_NAME_PARSE_FAILED", message));
    }

    @Test
    void finalConfirmationFailurePointsToManualResolutionButtons() {
        String result = TradeErrorGuidance.ensureGuidance(
                "FINAL_CONFIRMATION_NOT_FOUND",
                "当前界面没有可继续操作的按钮");

        assertTrue(result.contains("没有可继续操作的按钮"));
        assertTrue(result.contains("复核为已完成"));
        assertTrue(result.contains("复核为已取消"));
    }
}
