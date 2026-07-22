package com.auto.trade;

import com.auto.entity.GameItemOrder;
import com.auto.entity.GameItemOrderDetail;
import com.auto.service.GameItemOrderDetailService;
import com.auto.service.GameItemOrderService;
import com.auto.service.GameScriptService;
import com.auto.service.RegionScriptService;
import com.auto.trade.statemachine.OrderDeliveryStateMachine;
import com.auto.ws.AgentRegistry;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.Instant;
import java.util.List;
import java.util.Map;

import static org.mockito.Mockito.never;
import static org.mockito.Mockito.eq;
import static org.mockito.Mockito.same;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.junit.jupiter.api.Assertions.assertThrows;

@ExtendWith(MockitoExtension.class)
class GreetingDispatchServiceTest {

    @Mock
    private RegionScriptService regionScriptService;
    @Mock
    private GameScriptService gameScriptService;
    @Mock
    private AgentRegistry agentRegistry;
    @Mock
    private GameItemOrderService orderService;
    @Mock
    private GameItemOrderDetailService orderDetailService;
    @Mock
    private TradeDispatchCoordinator tradeDispatchCoordinator;
    @Mock
    private OrderDeliveryStateMachine stateMachine;

    @InjectMocks
    private GreetingDispatchService service;

    @Test
    void successfulGreetingDelegatesTheSingleStateTransitionToCoordinator() {
        int orderId = 42;
        GameItemOrder order = new GameItemOrder();
        order.setId(orderId);
        order.setDeliveryStatus("greeting");
        order.setStatus("pending");

        GameItemOrderDetail detail = new GameItemOrderDetail();
        detail.setOrderId(orderId);

        TradeOffer offer = new TradeOffer(
                "assignment-1",
                orderId,
                7,
                9,
                "token",
                Instant.now().plusSeconds(30),
                Map.of());

        when(orderService.getById(orderId)).thenReturn(order);
        when(orderDetailService.findByOrderId(orderId)).thenReturn(List.of(detail));
        when(tradeDispatchCoordinator.dispatch(orderId)).thenReturn(offer);

        service.handleResult(orderId, true, "ok");

        verify(tradeDispatchCoordinator).dispatch(orderId);
        verify(stateMachine, never()).fire(
                org.mockito.ArgumentMatchers.any(),
                org.mockito.ArgumentMatchers.any(),
                org.mockito.ArgumentMatchers.any());
    }

    @Test
    void failedGreetingIncludesErrorDetailsInStateTransition() {
        int orderId = 43;
        GameItemOrder order = new GameItemOrder();
        order.setId(orderId);
        order.setDeliveryStatus("greeting");
        order.setStatus("pending");
        when(orderService.getById(orderId)).thenReturn(order);

        service.handleResult(orderId, false, "聊天窗口发送失败");

        verify(stateMachine).fire(
                same(order),
                eq(com.auto.trade.statemachine.DeliveryEvent.GREETING_FAILED),
                org.mockito.ArgumentMatchers.argThat(context ->
                        "GREETING_EXECUTION_FAILED".equals(context.get("errorCode"))
                                && String.valueOf(context.get("errorMessage")).contains("原因：聊天窗口发送失败")
                                && String.valueOf(context.get("errorMessage")).contains("解决方案：")));
    }

    @Test
    void processingExceptionIsPersistedSeparately() {
        int orderId = 44;
        GameItemOrder order = new GameItemOrder();
        order.setId(orderId);
        order.setDeliveryStatus("greeting");
        order.setStatus("pending");
        when(orderService.getById(orderId)).thenReturn(order);
        doThrow(new IllegalStateException("状态写入失败"))
                .when(stateMachine)
                .fire(
                        org.mockito.ArgumentMatchers.any(),
                        org.mockito.ArgumentMatchers.any(),
                        org.mockito.ArgumentMatchers.any());

        assertThrows(IllegalStateException.class,
                () -> service.handleResult(orderId, false, "招呼失败"));

        verify(orderService).updateLastError(
                eq(orderId),
                eq("GREETING_RESULT_PROCESSING_ERROR"),
                org.mockito.ArgumentMatchers.argThat(message ->
                        message.contains("原因：状态写入失败")
                                && message.contains("解决方案：")));
    }
}
