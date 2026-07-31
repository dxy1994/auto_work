package com.auto.trade;

import com.auto.entity.GameItemOrder;
import com.auto.entity.TradeEvent;
import com.auto.service.GameItemOrderService;
import com.auto.service.TradeEventService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class DeliveryConfirmationServiceTest {

    private ChatDispatchService chatDispatchService;
    private GameItemOrderService orderService;
    private ManualOrderStatusService manualOrderStatusService;
    private TradeEventService tradeEventService;
    private DeliveryConfirmationService service;

    @BeforeEach
    void setUp() {
        chatDispatchService = mock(ChatDispatchService.class);
        orderService = mock(GameItemOrderService.class);
        manualOrderStatusService = mock(ManualOrderStatusService.class);
        tradeEventService = mock(TradeEventService.class);
        service = new DeliveryConfirmationService(
                chatDispatchService,
                orderService,
                manualOrderStatusService,
                tradeEventService);
    }

    @Test
    void dispatchRecordsRustfsPathAndSendsCombinedCommand() {
        GameItemOrder order = waitingOrder();
        when(orderService.getById(42)).thenReturn(order);
        when(chatDispatchService.dispatchDeliveryConfirmation(42))
                .thenReturn(new ChatDispatchService.DispatchReceipt(
                        "request-1", 42, 7, "itemmania", 1, 1));

        service.dispatch(42);

        verify(chatDispatchService).dispatchDeliveryConfirmation(42);
        ArgumentCaptor<TradeEvent> event = ArgumentCaptor.forClass(TradeEvent.class);
        verify(tradeEventService, org.mockito.Mockito.times(2)).save(event.capture());
        assertEquals(
                "trade_screenshot_stored",
                event.getAllValues().get(0).getEventType());
        assertEquals(
                "/uploads/trade-screenshots/2026/07/29/proof.png",
                event.getAllValues().get(0).getPayload().get("screenshot_path"));
        assertEquals(
                "delivery_confirmation_dispatched",
                event.getAllValues().get(1).getEventType());
    }

    @Test
    void successfulResultCompletesOrderAndClearsPreviousError() {
        GameItemOrder order = waitingOrder();
        when(orderService.getById(42)).thenReturn(order);

        service.handleResult(
                7,
                "request-1",
                42,
                true,
                "ok",
                java.util.Map.of(
                        "chat_sent", true,
                        "chat_closed", true,
                        "delivery_confirmed", true));

        verify(chatDispatchService).handleResult(
                7, "request-1", 42, true, "交易截图已发送");
        verify(manualOrderStatusService).complete(42);
        verify(orderService).updateLastError(42, null, null);
        ArgumentCaptor<TradeEvent> event = ArgumentCaptor.forClass(TradeEvent.class);
        verify(tradeEventService, org.mockito.Mockito.times(2)).save(event.capture());
        assertEquals("delivery_proof_sent", event.getAllValues().get(0).getEventType());
        assertEquals(
                "delivery_confirmation_completed",
                event.getAllValues().get(1).getEventType());
        assertEquals(
                "completed",
                event.getAllValues().get(1).getToStatus());
        assertEquals("ok", event.getAllValues().get(1).getMessage());
    }

    @Test
    void failedResultKeepsOrderWaitingAndRecordsActionableError() {
        GameItemOrder order = waitingOrder();
        when(orderService.getById(42)).thenReturn(order);

        service.handleResult(
                7,
                "request-1",
                42,
                false,
                "按钮不存在",
                java.util.Map.of(
                        "chat_sent", true,
                        "chat_closed", true,
                        "delivery_confirmed", false));

        verify(manualOrderStatusService, never()).complete(any());
        verify(orderService).updateLastError(
                org.mockito.ArgumentMatchers.eq(42),
                org.mockito.ArgumentMatchers.eq("WEBSITE_DELIVERY_CONFIRM_FAILED"),
                org.mockito.ArgumentMatchers.contains("按钮不存在"));
        ArgumentCaptor<TradeEvent> event = ArgumentCaptor.forClass(TradeEvent.class);
        verify(tradeEventService, org.mockito.Mockito.times(2)).save(event.capture());
        assertEquals("delivery_proof_sent", event.getAllValues().get(0).getEventType());
        assertEquals(
                "delivery_confirmation_failed",
                event.getAllValues().get(1).getEventType());
    }

    @Test
    void incompleteStructuredResultCannotCompleteOrder() {
        GameItemOrder order = waitingOrder();
        when(orderService.getById(42)).thenReturn(order);

        service.handleResult(
                7,
                "request-1",
                42,
                true,
                "ok",
                java.util.Map.of(
                        "chat_sent", true,
                        "chat_closed", false,
                        "delivery_confirmed", true));

        verify(manualOrderStatusService, never()).complete(any());
        verify(orderService).updateLastError(
                org.mockito.ArgumentMatchers.eq(42),
                org.mockito.ArgumentMatchers.eq("WEBSITE_DELIVERY_CONFIRM_FAILED"),
                org.mockito.ArgumentMatchers.contains("聊天页关闭失败"));
        ArgumentCaptor<TradeEvent> event = ArgumentCaptor.forClass(TradeEvent.class);
        verify(tradeEventService, org.mockito.Mockito.times(2)).save(event.capture());
        assertEquals("delivery_proof_failed", event.getAllValues().get(0).getEventType());
        assertEquals(
                "delivery_confirmation_failed",
                event.getAllValues().get(1).getEventType());
    }

    private static GameItemOrder waitingOrder() {
        GameItemOrder order = new GameItemOrder();
        order.setId(42);
        order.setAssignmentId("assignment-1");
        order.setDeliveryStatus("wait_web_confirm");
        order.setStatus("processing");
        order.setGameTradeScreenshot(
                "/uploads/trade-screenshots/2026/07/29/proof.png");
        return order;
    }
}
