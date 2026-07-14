package com.auto.trade;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class TradeDeliveryStatusTest {

    @Test
    void allowsOfferThenAssignment() {
        assertThat(TradeDeliveryStatus.WAITING_ASSIGNMENT
                .canMoveTo(TradeDeliveryStatus.OFFERED)).isTrue();
        assertThat(TradeDeliveryStatus.OFFERED
                .canMoveTo(TradeDeliveryStatus.ASSIGNED)).isTrue();
    }

    @Test
    void gameDeliveredCannotReturnToGameExecution() {
        assertThat(TradeDeliveryStatus.GAME_DELIVERED
                .canMoveTo(TradeDeliveryStatus.ASSIGNED)).isFalse();
        assertThatThrownBy(() -> TradeDeliveryStatus.GAME_DELIVERED
                .requireMoveTo(TradeDeliveryStatus.ASSIGNED))
                .isInstanceOf(IllegalStateException.class);
    }

    @Test
    void gameDeliveredCanRetryWebsiteConfirmation() {
        assertThat(TradeDeliveryStatus.GAME_DELIVERED
                .canMoveTo(TradeDeliveryStatus.WEBSITE_CONFIRMING)).isTrue();
        assertThat(TradeDeliveryStatus.WEBSITE_CONFIRMING
                .canMoveTo(TradeDeliveryStatus.GAME_DELIVERED)).isTrue();
    }
}
