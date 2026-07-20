package com.auto.trade;

import com.auto.entity.GameItemOrder;
import com.auto.entity.TradeAssignment;
import com.auto.service.GameItemOrderService;
import com.auto.service.TradeAssignmentService;
import com.auto.trade.statemachine.DeliveryEvent;
import com.auto.trade.statemachine.OrderDeliveryStateMachine;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class TradeRecoveryServiceTest {

    @Test
    @SuppressWarnings("unchecked")
    void lostMachineMovesAcceptedOrderBackToWaitingAssignment() {
        TradeAssignmentService assignmentService = mock(TradeAssignmentService.class);
        GameItemOrderService orderService = mock(GameItemOrderService.class);
        OrderDeliveryStateMachine stateMachine = mock(OrderDeliveryStateMachine.class);
        TradeRecoveryService service = new TradeRecoveryService(
                assignmentService, orderService, stateMachine);

        TradeAssignment assignment = new TradeAssignment();
        assignment.setAssignmentId("assignment-1");
        assignment.setOrderId(42);
        assignment.setMachineId(7);
        assignment.setGameAccountId(9);
        assignment.setStatus("accepted");

        GameItemOrder order = new GameItemOrder();
        order.setId(42);
        order.setDeliveryStatus("assigned");
        order.setStatus("pending");

        when(orderService.getById(42)).thenReturn(order);

        service.recover(assignment, "worker 断线");

        ArgumentCaptor<Map<String, Object>> contextCaptor = ArgumentCaptor.forClass(Map.class);
        verify(stateMachine).fire(
                eq(order), eq(DeliveryEvent.WORKER_DISCONNECTED), contextCaptor.capture());
        assertEquals("assignment-1", contextCaptor.getValue().get("assignmentId"));
        assertEquals("WORKER_DISCONNECTED", contextCaptor.getValue().get("errorCode"));
    }
}
