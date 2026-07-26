package com.auto.trade;

import com.auto.entity.GameItemOrder;
import com.auto.entity.GameItemOrderDetail;
import com.auto.entity.TradeAssignment;
import com.auto.service.GameItemOrderDetailService;
import com.auto.service.GameItemOrderService;
import com.auto.service.TradeAssignmentService;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class ManualOrderStatusServiceTest {

    @Mock
    private GameItemOrderService orderService;
    @Mock
    private GameItemOrderDetailService detailService;
    @Mock
    private TradeAssignmentService assignmentService;
    @Mock
    private TradeCompletionService completionService;

    @InjectMocks
    private ManualOrderStatusService statusService;

    @Test
    void completingOrderSynchronizesOrderAndDeliveryStatus() {
        GameItemOrder order = order("greeting", "pending");
        when(orderService.getOne(any(), eq(false))).thenReturn(order);

        statusService.complete(42);

        verify(completionService).complete(order);
        assertEquals("completed", order.getStatus());
        assertEquals("completed", order.getDeliveryStatus());
        verify(orderService).updateById(order);
    }

    @Test
    void cancellingOrderCancelsDetailsAndClearsStaleAssignment() {
        GameItemOrder order = order("suspended", "pending");
        order.setAssignmentId("assignment-1");
        order.setAssignedMachineId(7);
        order.setGameAccountId(9);
        order.setLastErrorCode("TRADE_EXECUTION_FAILED");
        GameItemOrderDetail detail = new GameItemOrderDetail();
        detail.setId(100);
        detail.setStatus("pending");
        when(orderService.getOne(any(), eq(false))).thenReturn(order);
        when(detailService.findByOrderId(42)).thenReturn(List.of(detail));

        statusService.cancel(42);

        assertEquals("cancelled", order.getStatus());
        assertEquals("cancelled", order.getDeliveryStatus());
        assertEquals("cancelled", detail.getStatus());
        assertNull(order.getAssignmentId());
        assertNull(order.getAssignedMachineId());
        assertNull(order.getGameAccountId());
        assertNull(order.getLastErrorCode());
        verify(detailService).updateById(detail);
        verify(orderService).updateById(order);
    }

    @Test
    void activeTradeCannotBeManuallyTerminated() {
        GameItemOrder order = order("assigned", "pending");
        when(orderService.getOne(any(), eq(false))).thenReturn(order);

        assertThrows(IllegalStateException.class, () -> statusService.complete(42));
        assertThrows(IllegalStateException.class, () -> statusService.cancel(42));

        verify(completionService, never()).complete(any());
        verify(orderService, never()).updateById(any());
    }

    @Test
    void reviewRequiredOrderCanBeResolvedAsCompleted() {
        GameItemOrder order = order("review_required", "pending");
        order.setAssignmentId("assignment-1");
        order.setAssignedMachineId(7);
        order.setGameAccountId(9);
        TradeAssignment assignment = assignment("assignment-1", "verification_failed");
        when(orderService.getOne(any(), eq(false))).thenReturn(order);
        when(assignmentService.getOne(any(), eq(false))).thenReturn(assignment);

        statusService.complete(42);

        verify(completionService).complete(order);
        assertEquals("completed", order.getStatus());
        assertEquals("completed", order.getDeliveryStatus());
        assertNull(order.getAssignmentId());
        assertNull(order.getAssignedMachineId());
        assertNull(order.getGameAccountId());
        assertEquals("manually_completed", assignment.getStatus());
        assertEquals("manual_complete", assignment.getRejectReason());
        verify(assignmentService).updateById(assignment);
    }

    @Test
    void reviewRequiredOrderCanBeResolvedAsCancelled() {
        GameItemOrder order = order("review_required", "pending");
        order.setAssignmentId("assignment-1");
        order.setLastErrorCode("FINAL_CONFIRMATION_NOT_FOUND");
        TradeAssignment assignment = assignment("assignment-1", "verification_failed");
        when(orderService.getOne(any(), eq(false))).thenReturn(order);
        when(detailService.findByOrderId(42)).thenReturn(List.of());
        when(assignmentService.getOne(any(), eq(false))).thenReturn(assignment);

        statusService.cancel(42);

        assertEquals("cancelled", order.getStatus());
        assertEquals("cancelled", order.getDeliveryStatus());
        assertNull(order.getAssignmentId());
        assertNull(order.getLastErrorCode());
        assertEquals("manually_cancelled", assignment.getStatus());
        assertEquals("manual_cancel", assignment.getRejectReason());
        verify(assignmentService).updateById(assignment);
        verify(orderService).updateById(order);
    }

    @Test
    void coordinatorCanCompleteQueuedOrderAndClearQueueBinding() {
        GameItemOrder order = order("queued", "pending");
        order.setAssignedMachineId(7);
        order.setGameAccountId(9);
        when(orderService.getOne(any(), eq(false))).thenReturn(order);

        statusService.completeAfterAutomationStopped(42);

        assertEquals("completed", order.getStatus());
        assertEquals("completed", order.getDeliveryStatus());
        assertNull(order.getAssignedMachineId());
        assertNull(order.getGameAccountId());
        verify(completionService).complete(order);
    }

    private static GameItemOrder order(String deliveryStatus, String status) {
        GameItemOrder order = new GameItemOrder();
        order.setId(42);
        order.setDeliveryStatus(deliveryStatus);
        order.setStatus(status);
        return order;
    }

    private static TradeAssignment assignment(String assignmentId, String status) {
        TradeAssignment assignment = new TradeAssignment();
        assignment.setAssignmentId(assignmentId);
        assignment.setStatus(status);
        return assignment;
    }
}
