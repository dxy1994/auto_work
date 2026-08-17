package com.auto.trade;

import com.auto.entity.GameItemOrder;
import com.auto.entity.TradeAssignment;
import com.auto.entity.TradeEvent;
import com.auto.service.TradeEventService;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

import java.time.LocalDateTime;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;

class BuyerReviewAuditServiceTest {

    @Test
    void recordsEachRejectedReviewAsAnOrderEvent() {
        TradeEventService tradeEventService = mock(TradeEventService.class);
        BuyerReviewAuditService service = new BuyerReviewAuditService(tradeEventService);

        GameItemOrder order = new GameItemOrder();
        order.setId(24);
        order.setOrderNo("ORDER-24");
        order.setBuyerCharacter("订单玩家");
        order.setDeliveryStatus("assigned");

        TradeAssignment first = assignment("assignment-1", "review-1", 1, "识别玩家甲");
        TradeAssignment second = assignment("assignment-2", "review-2", 2, "识别玩家乙");

        service.recordRejected(order, first);
        service.recordRejected(order, second);

        ArgumentCaptor<TradeEvent> eventCaptor = ArgumentCaptor.forClass(TradeEvent.class);
        verify(tradeEventService, times(2)).save(eventCaptor.capture());
        List<TradeEvent> events = eventCaptor.getAllValues();
        assertEquals("buyer_review_rejected", events.get(0).getEventType());
        assertEquals(24, events.get(0).getOrderId());
        assertEquals("rejected", events.get(0).getPayload().get("decision"));
        assertTrue(events.get(0).getMessage().contains("机器#1"));
        assertTrue(events.get(0).getMessage().contains("识别玩家甲"));
    }

    private static TradeAssignment assignment(
            String assignmentId, String reviewId, int machineId, String observedBuyer) {
        TradeAssignment assignment = new TradeAssignment();
        assignment.setAssignmentId(assignmentId);
        assignment.setBuyerReviewId(reviewId);
        assignment.setMachineId(machineId);
        assignment.setGameAccountId(9);
        assignment.setExpectedBuyerName("订单玩家");
        assignment.setObservedBuyerName(observedBuyer);
        assignment.setBuyerOcrConfidence(94.2);
        assignment.setBuyerReviewDecidedAt(LocalDateTime.now());
        return assignment;
    }
}
