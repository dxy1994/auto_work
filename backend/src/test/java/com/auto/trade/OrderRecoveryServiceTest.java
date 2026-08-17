package com.auto.trade;

import com.auto.entity.GameItemOrder;
import com.auto.entity.GameItemOrderDetail;
import com.auto.service.GameItemOrderService;
import com.auto.trade.statemachine.DeliveryEvent;
import com.auto.trade.statemachine.OrderDeliveryStateMachine;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InOrder;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.inOrder;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class OrderRecoveryServiceTest {

    @Mock
    private GameItemOrderService orderService;
    @Mock
    private OrderDetailGenerationService detailGenerationService;
    @Mock
    private OrderDeliveryStateMachine stateMachine;

    @InjectMocks
    private OrderRecoveryService recoveryService;

    @Test
    void restoresPreErrorStateBeforeExecutingTheFailedStep() {
        GameItemOrder order = new GameItemOrder();
        order.setId(42);
        order.setDeliveryStatus("greeting");
        order.setStatus("abnormal");
        order.setLastErrorCode("SUB_ORDER_MISSING");
        GameItemOrderDetail detail = new GameItemOrderDetail();

        when(orderService.getById(42)).thenReturn(order);
        when(detailGenerationService.ensureDetails(order)).thenReturn(List.of(detail));

        List<GameItemOrderDetail> result = recoveryService.recoverMissingSubOrder(42);

        assertEquals(List.of(detail), result);
        InOrder sequence = inOrder(stateMachine, detailGenerationService);
        sequence.verify(stateMachine).fire(
                org.mockito.ArgumentMatchers.same(order),
                org.mockito.ArgumentMatchers.eq(DeliveryEvent.RESET_TO_GREETING),
                any());
        sequence.verify(detailGenerationService).ensureDetails(order);
    }
}
