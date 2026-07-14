package com.auto.controller;

import com.auto.service.GameItemOrderService;
import com.auto.trade.TradeDispatchCoordinator;
import com.auto.trade.TradeOffer;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class TradeDispatchControllerTest {

    @Test
    void dispatchResponseNeverExposesExecutionToken() {
        TradeDispatchCoordinator coordinator = mock(TradeDispatchCoordinator.class);
        TradeOffer offer = new TradeOffer(
                "a-1", 55, 7, 101, "top-secret", Instant.parse("2030-01-01T00:00:00Z"), Map.of());
        when(coordinator.dispatch(55)).thenReturn(offer);
        TradeDispatchController controller = new TradeDispatchController(
                coordinator, mock(GameItemOrderService.class));

        Map<String, Object> response = controller.dispatch(55);

        assertThat(response).doesNotContainKeys("execution_token", "executionToken");
        assertThat(response.toString()).doesNotContain("top-secret");
    }
}
