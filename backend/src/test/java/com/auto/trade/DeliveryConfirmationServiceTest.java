package com.auto.trade;

import com.auto.entity.GameItemOrder;
import com.auto.entity.GameScript;
import com.auto.entity.RegionScript;
import com.auto.entity.TradeEvent;
import com.auto.service.GameItemOrderService;
import com.auto.service.GameScriptService;
import com.auto.service.RegionScriptService;
import com.auto.service.TradeEventService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyBoolean;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class DeliveryConfirmationServiceTest {

    private ChatDispatchService chatDispatchService;
    private GameItemOrderService orderService;
    private ManualOrderStatusService manualOrderStatusService;
    private TradeEventService tradeEventService;
    private GameScriptService gameScriptService;
    private RegionScriptService regionScriptService;
    private DeliveryConfirmationService service;

    @BeforeEach
    void setUp() {
        chatDispatchService = mock(ChatDispatchService.class);
        orderService = mock(GameItemOrderService.class);
        manualOrderStatusService = mock(ManualOrderStatusService.class);
        tradeEventService = mock(TradeEventService.class);
        gameScriptService = mock(GameScriptService.class);
        regionScriptService = mock(RegionScriptService.class);
        service = new DeliveryConfirmationService(
                chatDispatchService,
                orderService,
                manualOrderStatusService,
                tradeEventService,
                gameScriptService,
                regionScriptService);
    }

    @Test
    void dispatchRecordsRustfsPathAndSendsCombinedCommand() {
        GameItemOrder order = waitingOrder();
        GameScript gameScript = new GameScript();
        gameScript.setContent("交易已经完成，谢谢");
        RegionScript regionScript = new RegionScript();
        regionScript.setImageUrl("/uploads/completed.png");
        when(orderService.getById(42)).thenReturn(order);
        when(gameScriptService.findAllByGameIdAndCategory(3, "交易完成"))
                .thenReturn(List.of(gameScript));
        when(regionScriptService.findAllByRegionIdAndCategory(4, "交易完成"))
                .thenReturn(List.of(regionScript));
        when(chatDispatchService.dispatchDeliveryConfirmation(
                org.mockito.ArgumentMatchers.eq(42), any()))
                .thenReturn(new ChatDispatchService.DispatchReceipt(
                        "request-1", 42, 7, "itemmania", 1, 1));

        service.dispatch(42);

        @SuppressWarnings("unchecked")
        ArgumentCaptor<List<Map<String, Object>>> messages =
                ArgumentCaptor.forClass(List.class);
        verify(chatDispatchService).dispatchDeliveryConfirmation(
                org.mockito.ArgumentMatchers.eq(42), messages.capture());
        assertEquals(2, messages.getValue().size());
        assertEquals("交易已经完成，谢谢", messages.getValue().get(0).get("content"));
        assertEquals(
                "/uploads/completed.png",
                messages.getValue().get(1).get("image_url"));
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
    void actionOnlyResultCompletesWithoutSendingProofAgain() {
        GameItemOrder order = waitingOrder();
        when(orderService.getById(42)).thenReturn(order);

        service.handleResult(
                7,
                "request-1",
                42,
                true,
                "ok",
                java.util.Map.of(
                        "chat_sent", false,
                        "chat_closed", true,
                        "proof_already_sent", true,
                        "delivery_confirmed", true));

        verify(chatDispatchService, never()).handleResult(
                anyInt(), anyString(), anyInt(), anyBoolean(), anyString());
        verify(manualOrderStatusService).complete(42);
        ArgumentCaptor<TradeEvent> event = ArgumentCaptor.forClass(TradeEvent.class);
        verify(tradeEventService, org.mockito.Mockito.times(2)).save(event.capture());
        assertEquals(
                "最终确认截图此前已发送，本次未重复发送",
                event.getAllValues().get(0).getMessage());
    }

    @Test
    void completionMessageFailureDoesNotBlockOrderCompletion() {
        GameItemOrder order = waitingOrder();
        when(orderService.getById(42)).thenReturn(order);

        service.handleResult(
                7,
                "request-1",
                42,
                true,
                "网站确认成功",
                Map.of(
                        "chat_sent", false,
                        "chat_closed", true,
                        "proof_already_sent", true,
                        "completion_message_error", "聊天输入框不可用",
                        "delivery_confirmed", true));

        verify(manualOrderStatusService).complete(42);
        verify(orderService).updateLastError(42, null, null);
        ArgumentCaptor<TradeEvent> event = ArgumentCaptor.forClass(TradeEvent.class);
        verify(tradeEventService, org.mockito.Mockito.times(3)).save(event.capture());
        assertEquals(
                "trade_completion_message_failed",
                event.getAllValues().get(0).getEventType());
        assertEquals("delivery_proof_sent", event.getAllValues().get(1).getEventType());
        assertEquals(
                "delivery_confirmation_completed",
                event.getAllValues().get(2).getEventType());
    }

    @Test
    void completionScriptLoadFailureFallsBackToActionOnlyDispatch() {
        GameItemOrder order = waitingOrder();
        when(orderService.getById(42)).thenReturn(order);
        when(gameScriptService.findAllByGameIdAndCategory(3, "交易完成"))
                .thenThrow(new IllegalStateException("话术数据库暂时不可用"));
        when(chatDispatchService.dispatchDeliveryConfirmation(
                org.mockito.ArgumentMatchers.eq(42),
                org.mockito.ArgumentMatchers.eq(List.of())))
                .thenReturn(new ChatDispatchService.DispatchReceipt(
                        "request-2", 42, 7, "itemmania", 0, 0));

        service.dispatch(42);

        verify(chatDispatchService).dispatchDeliveryConfirmation(42, List.of());
        verify(orderService, never()).updateLastError(
                org.mockito.ArgumentMatchers.eq(42),
                org.mockito.ArgumentMatchers.anyString(),
                org.mockito.ArgumentMatchers.anyString());
        ArgumentCaptor<TradeEvent> event = ArgumentCaptor.forClass(TradeEvent.class);
        verify(tradeEventService, org.mockito.Mockito.times(3)).save(event.capture());
        assertEquals(
                "trade_completion_message_failed",
                event.getAllValues().get(0).getEventType());
        assertEquals(
                "delivery_confirmation_dispatched",
                event.getAllValues().get(2).getEventType());
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
        order.setGameId(3);
        order.setRegionId(4);
        order.setGameTradeScreenshot(
                "/uploads/trade-screenshots/2026/07/29/proof.png");
        return order;
    }
}
