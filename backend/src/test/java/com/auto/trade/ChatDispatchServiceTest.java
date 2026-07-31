package com.auto.trade;

import com.auto.common.ApiException;
import com.auto.entity.GameItemOrder;
import com.auto.entity.MachinePlatformAccount;
import com.auto.entity.Platform;
import com.auto.entity.PlatformAccount;
import com.auto.entity.TradeEvent;
import com.auto.service.GameItemOrderService;
import com.auto.service.MachinePlatformAccountService;
import com.auto.service.PlatformAccountService;
import com.auto.service.PlatformService;
import com.auto.service.TradeEventService;
import com.auto.ws.AgentRegistry;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyList;
import static org.mockito.ArgumentMatchers.anyMap;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class ChatDispatchServiceTest {

    @Mock
    private GameItemOrderService orderService;
    @Mock
    private PlatformAccountService accountService;
    @Mock
    private MachinePlatformAccountService machinePlatformAccountService;
    @Mock
    private PlatformService platformService;
    @Mock
    private TradeEventService tradeEventService;
    @Mock
    private AgentRegistry agentRegistry;

    @InjectMocks
    private ChatDispatchService service;

    @Test
    void manualChatUsesTheOrderSourceAccountAndKeepsMessageOrder() {
        GameItemOrder order = itemManiaOrder();
        PlatformAccount account = new PlatformAccount();
        account.setId(5);
        account.setWebsiteId(1);
        account.setIsActive(1);
        MachinePlatformAccount binding = new MachinePlatformAccount();
        binding.setMachineId(7);
        binding.setAccountId(5);

        when(orderService.getById(42)).thenReturn(order);
        when(accountService.getById(5)).thenReturn(account);
        when(machinePlatformAccountService.findByAccountIdActive(5))
                .thenReturn(List.of(binding));
        when(agentRegistry.pickAgent(7)).thenReturn(7);
        when(platformService.getById(1)).thenReturn(itemMania());
        when(agentRegistry.sendChat(
                anyInt(), anyString(), anyInt(), anyInt(), anyInt(), anyString(),
                anyString(), anyString(), anyList(), anyMap()))
                .thenReturn(true);

        ChatDispatchService.DispatchReceipt receipt = service.dispatchOrderChat(
                42,
                List.of(
                        Map.of("type", "text", "content", "第一条"),
                        Map.of(
                                "type", "mixed",
                                "content", "第二条",
                                "image_urls", List.of("/uploads/a.png", "/uploads/b.png"))));

        assertEquals(7, receipt.machineId());
        assertEquals(2, receipt.messageCount());
        assertEquals(2, receipt.imageCount());

        @SuppressWarnings("unchecked")
        ArgumentCaptor<List<Map<String, Object>>> messages =
                ArgumentCaptor.forClass(List.class);
        @SuppressWarnings("unchecked")
        ArgumentCaptor<Map<String, Object>> target =
                ArgumentCaptor.forClass(Map.class);
        verify(agentRegistry).sendChat(
                anyInt(), anyString(), anyInt(), anyInt(), anyInt(), anyString(),
                anyString(), anyString(), messages.capture(), target.capture());

        assertEquals("第一条", messages.getValue().get(0).get("content"));
        assertEquals("第二条", messages.getValue().get(1).get("content"));
        assertEquals(
                List.of("/uploads/a.png", "/uploads/b.png"),
                messages.getValue().get(1).get("image_urls"));
        assertTrue(target.getValue().get("url").toString().contains("tid=IM-2026-42"));
        assertEquals("#write_chat", target.getValue().get("input_selector"));
    }

    @Test
    void deliveryConfirmationSendsStoredProofThenRequestsPlatformConfirmation() {
        GameItemOrder order = itemManiaOrder();
        order.setDeliveryStatus("wait_web_confirm");
        order.setStatus("processing");
        order.setGameTradeScreenshot(
                "/uploads/trade-screenshots/2026/07/29/proof.png");
        PlatformAccount account = new PlatformAccount();
        account.setId(5);
        account.setWebsiteId(1);
        account.setIsActive(1);
        MachinePlatformAccount binding = new MachinePlatformAccount();
        binding.setMachineId(7);
        binding.setAccountId(5);

        when(orderService.getById(42)).thenReturn(order);
        when(accountService.getById(5)).thenReturn(account);
        when(machinePlatformAccountService.findByAccountIdActive(5))
                .thenReturn(List.of(binding));
        when(agentRegistry.pickAgent(7)).thenReturn(7);
        when(platformService.getById(1)).thenReturn(itemMania());
        when(agentRegistry.sendChat(
                anyInt(), anyString(), anyInt(), anyInt(), anyInt(), anyString(),
                anyString(), anyString(), anyList(), anyMap(), anyMap()))
                .thenReturn(true);

        ChatDispatchService.DispatchReceipt receipt =
                service.dispatchDeliveryConfirmation(42);

        @SuppressWarnings("unchecked")
        ArgumentCaptor<List<Map<String, Object>>> messages =
                ArgumentCaptor.forClass(List.class);
        @SuppressWarnings("unchecked")
        ArgumentCaptor<Map<String, Object>> action =
                ArgumentCaptor.forClass(Map.class);
        verify(agentRegistry).sendChat(
                anyInt(), anyString(), anyInt(), anyInt(), anyInt(), anyString(),
                anyString(), anyString(), messages.capture(), anyMap(), action.capture());

        assertEquals(1, receipt.imageCount());
        assertEquals(
                List.of("/uploads/trade-screenshots/2026/07/29/proof.png"),
                messages.getValue().get(0).get("image_urls"));
        assertEquals("confirm_delivery", action.getValue().get("type"));
        assertTrue(action.getValue().get("detail_url").toString()
                .contains("sell_ing_view.html?id=IM-2026-42"));
        assertEquals("#trade_btn", action.getValue().get("open_confirm_selector"));
        assertEquals(".caution_list .caution", action.getValue().get("stage_selector"));
        assertEquals(3, action.getValue().get("pending_stage"));
    }

    @Test
    void configuredPlatformRequiresImageSendSelectorWhenUploadIsNotAutomatic() {
        GameItemOrder order = itemManiaOrder();
        Platform platform = itemMania();
        platform.setName("Other Market");
        platform.setUrl("https://market.example.com/login");
        platform.setLoginConfig(Map.of(
                "chat_config",
                Map.of(
                        "url_template", "https://market.example.com/chat/{order_no}",
                        "input_selector", "#input",
                        "send_selector", "#send",
                        "file_selector", "#file",
                        "upload_auto_send", false)));

        when(orderService.getById(order.getId())).thenReturn(order);
        when(platformService.getById(order.getWebsiteId())).thenReturn(platform);

        ApiException error = assertThrows(
                ApiException.class,
                () -> service.dispatchGreeting(
                        7,
                        order.getId(),
                        order.getWebsiteId(),
                        order.getPlatformAccountId(),
                        order.getSourceOrderNo(),
                        "other",
                        List.of(Map.of("image_url", "/uploads/a.png"))));
        assertTrue(error.getMessage().contains("图片上传后的发送按钮"));
    }

    @Test
    void manualChatResultOnlyAppendsAnEvent() {
        GameItemOrder order = itemManiaOrder();
        order.setDeliveryStatus("assigned");
        when(orderService.getById(42)).thenReturn(order);

        service.handleResult(7, "request-1", 42, true, "ok");

        ArgumentCaptor<TradeEvent> event = ArgumentCaptor.forClass(TradeEvent.class);
        verify(tradeEventService).save(event.capture());
        assertEquals("chat_message_sent", event.getValue().getEventType());
        assertEquals("assigned", event.getValue().getFromStatus());
        assertEquals("assigned", event.getValue().getToStatus());
    }

    @Test
    void rejectsEmptyMessage() {
        assertThrows(ApiException.class, () -> service.normalizeMessages(List.of(Map.of())));
    }

    private GameItemOrder itemManiaOrder() {
        GameItemOrder order = new GameItemOrder();
        order.setId(42);
        order.setWebsiteId(1);
        order.setPlatformAccountId(5);
        order.setSourceOrderNo("IM-2026-42");
        order.setDeliveryStatus("greeting");
        order.setStatus("pending");
        return order;
    }

    private Platform itemMania() {
        Platform platform = new Platform();
        platform.setId(1);
        platform.setName("ItemMania");
        platform.setUrl("https://www.itemmania.com/login");
        platform.setIsActive(1);
        platform.setLoginConfig(Map.of());
        return platform;
    }
}
