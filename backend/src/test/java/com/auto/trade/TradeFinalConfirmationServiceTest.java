package com.auto.trade;

import com.auto.entity.GameItemOrder;
import com.auto.entity.GameScript;
import com.auto.entity.TradeAssignment;
import com.auto.service.GameItemOrderService;
import com.auto.service.GameScriptService;
import com.auto.service.RegionScriptService;
import com.auto.service.TradeAssignmentService;
import com.auto.service.TradeEventService;
import com.auto.ws.AgentRegistry;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyBoolean;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class TradeFinalConfirmationServiceTest {

    private ChatDispatchService chatDispatchService;
    private GameItemOrderService orderService;
    private AgentRegistry agentRegistry;
    private TradeFinalConfirmationService service;

    @BeforeEach
    void setUp() {
        orderService = mock(GameItemOrderService.class);
        TradeAssignmentService assignmentService = mock(TradeAssignmentService.class);
        GameScriptService gameScriptService = mock(GameScriptService.class);
        RegionScriptService regionScriptService = mock(RegionScriptService.class);
        chatDispatchService = mock(ChatDispatchService.class);
        TradeEventService tradeEventService = mock(TradeEventService.class);
        agentRegistry = mock(AgentRegistry.class);
        service = new TradeFinalConfirmationService(
                orderService,
                assignmentService,
                gameScriptService,
                regionScriptService,
                chatDispatchService,
                tradeEventService,
                agentRegistry);

        TradeAssignment assignment = new TradeAssignment();
        assignment.setAssignmentId("assignment-1");
        assignment.setOrderId(42);
        assignment.setMachineId(9);
        when(assignmentService.getOne(any(), eq(false))).thenReturn(assignment);

        GameItemOrder order = new GameItemOrder();
        order.setId(42);
        order.setAssignmentId("assignment-1");
        order.setGameId(3);
        order.setRegionId(4);
        order.setDeliveryStatus("trading");
        when(orderService.getById(42)).thenReturn(order);

        GameScript script = new GameScript();
        script.setContent("거래 내용을 확인하고 네라고 답해주세요");
        when(gameScriptService.findAllByGameIdAndCategory(3, "确认"))
                .thenReturn(List.of(script));
        when(regionScriptService.findAllByRegionIdAndCategory(4, "确认"))
                .thenReturn(List.of());
        when(chatDispatchService.dispatchTradeFinalConfirmation(
                eq(42), eq("request-1"), any()))
                .thenReturn(new ChatDispatchService.DispatchReceipt(
                        "request-1", 42, 7, "barotem", 2, 1));
        when(agentRegistry.sendTradeFinalConfirmationResult(
                eq(9), eq("request-1"), anyBoolean(),
                anyBoolean(), any(), any()))
                .thenReturn(true);
    }

    @Test
    void sendsConfirmationScriptsAndScreenshotBeforeWaiting() {
        service.begin(
                "assignment-1",
                9,
                "request-1",
                "/uploads/trade-screenshots/proof.png");

        @SuppressWarnings("unchecked")
        ArgumentCaptor<List<Map<String, Object>>> messages =
                ArgumentCaptor.forClass(List.class);
        verify(chatDispatchService).dispatchTradeFinalConfirmation(
                eq(42), eq("request-1"), messages.capture());
        assertEquals(2, messages.getValue().size());
        assertEquals(
                "/uploads/trade-screenshots/proof.png",
                messages.getValue().get(1).get("image_url"));
    }

    @Test
    void anyNonAffirmativeReplyRejectsFinalGameConfirmation() {
        service.begin(
                "assignment-1",
                9,
                "request-1",
                "/uploads/trade-screenshots/proof.png");

        service.handleChatResult(
                7,
                "request-1",
                42,
                false,
                "买家回复不是韩文肯定答复",
                Map.of(
                        "reply_received", true,
                        "affirmative_reply", false,
                        "reply_text", "아니요"));

        verify(agentRegistry).sendTradeFinalConfirmationResult(
                9,
                "request-1",
                false,
                true,
                "아니요",
                "买家回复不是韩文肯定答复");
    }

    @Test
    void affirmativeKoreanReplyApprovesFinalGameConfirmation() {
        service.begin(
                "assignment-1",
                9,
                "request-1",
                "/uploads/trade-screenshots/proof.png");

        service.handleChatResult(
                7,
                "request-1",
                42,
                true,
                "已收到买家韩文肯定回复",
                Map.of(
                        "reply_received", true,
                        "affirmative_reply", true,
                        "reply_text", "네"));

        verify(agentRegistry).sendTradeFinalConfirmationResult(
                9, "request-1", true, true, "네", "");
    }

    @Test
    void completedGameTradeCannotSendFinalScreenshotAgain() {
        GameItemOrder order = new GameItemOrder();
        order.setId(42);
        order.setAssignmentId("assignment-1");
        order.setStatus("processing");
        order.setDeliveryStatus("wait_web_confirm");
        when(orderService.getById(42)).thenReturn(order);

        IllegalStateException error = assertThrows(
                IllegalStateException.class,
                () -> service.begin(
                        "assignment-1",
                        9,
                        "request-1",
                        "/uploads/trade-screenshots/proof.png"));

        assertEquals("游戏交易已经完成，无需再次发送最终确认图片", error.getMessage());
    }
}
