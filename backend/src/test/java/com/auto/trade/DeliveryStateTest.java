package com.auto.trade;

import com.auto.trade.statemachine.DeliveryState;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

class DeliveryStateTest {

    @Test
    void gameTradeCompletionWaitsForWebsiteConfirmation() {
        assertEquals(
                DeliveryState.WAIT_WEB_CONFIRM,
                DeliveryState.from("wait_web_confirm", "processing"));
    }

    @Test
    void greetingAbnormalIsARecognizedOrderState() {
        assertEquals(
                DeliveryState.GREETING_ABNORMAL,
                DeliveryState.from("greeting", "abnormal"));
    }
}
