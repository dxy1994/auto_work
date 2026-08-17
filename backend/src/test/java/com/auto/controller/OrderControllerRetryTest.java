package com.auto.controller;

import com.auto.common.ApiException;
import com.auto.entity.GameItemOrder;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

class OrderControllerRetryTest {

    @Test
    void retriesGreetingWhenGreetingExecutionFailed() {
        GameItemOrder order = order("greeting", "pending", null, "GREETING_EXECUTION_FAILED");

        assertEquals(OrderController.RetryStage.GREETING,
                OrderController.resolveRetryStage(order));
    }

    @Test
    void skipsRepeatedGreetingWhenTradeDispatchFailed() {
        GameItemOrder order = order("greeting", "pending", null, "TRADE_DISPATCH_FAILED");

        assertEquals(OrderController.RetryStage.ASSIGNMENT,
                OrderController.resolveRetryStage(order));
    }

    @Test
    void missingSubOrderRetriesOnlySubOrderGeneration() {
        GameItemOrder order = order("greeting", "abnormal", null, "SUB_ORDER_MISSING");

        assertEquals(OrderController.RetryStage.SUB_ORDER_GENERATION,
                OrderController.resolveRetryStage(order));
    }

    @Test
    void retriesSuspendedTradeFromAssignmentStage() {
        GameItemOrder order = order("suspended", "pending", "assignment-1", "TRADE_EXECUTION_FAILED");

        assertEquals(OrderController.RetryStage.ASSIGNMENT,
                OrderController.resolveRetryStage(order));
    }

    @Test
    void retriesSuspendedGreetingFromGreetingStage() {
        GameItemOrder order = order("suspended", "pending", null, "GREETING_FAILED");

        assertEquals(OrderController.RetryStage.GREETING,
                OrderController.resolveRetryStage(order));
    }

    @Test
    void doesNotRetryAnIngestionConfigurationFailureWithoutRepairingTheOrder() {
        GameItemOrder order = order("suspended", "pending", null, "CONFIG_MISSING");

        ApiException error = assertThrows(ApiException.class,
                () -> OrderController.resolveRetryStage(order));

        assertEquals(400, error.getStatus().value());
    }

    @Test
    void doesNotRetryAnUncertainTradeResult() {
        GameItemOrder order = order("review_required", "pending", "assignment-2", "TRADE_RESULT_UNCERTAIN");

        ApiException error = assertThrows(ApiException.class,
                () -> OrderController.resolveRetryStage(order));

        assertEquals(409, error.getStatus().value());
    }

    private static GameItemOrder order(
            String deliveryStatus,
            String status,
            String assignmentId,
            String errorCode) {
        GameItemOrder order = new GameItemOrder();
        order.setDeliveryStatus(deliveryStatus);
        order.setStatus(status);
        order.setAssignmentId(assignmentId);
        order.setLastErrorCode(errorCode);
        return order;
    }
}
