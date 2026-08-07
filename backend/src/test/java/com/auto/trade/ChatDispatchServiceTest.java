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
import static org.mockito.ArgumentMatchers.eq;
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
    void deliveryConfirmationSkipsPreviouslySentProofAndRequestsPlatformConfirmation() {
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

        assertEquals(0, receipt.imageCount());
        assertEquals(List.of(), messages.getValue());
        assertEquals("confirm_delivery", action.getValue().get("type"));
        assertEquals(true, action.getValue().get("skip_chat"));
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
    void itemBayUsesLiveBayTalkDefaultsAndTransactionId() {
        GameItemOrder order = itemBayOrder();
        PlatformAccount account = new PlatformAccount();
        account.setId(6);
        account.setWebsiteId(2);
        account.setIsActive(1);
        MachinePlatformAccount binding = new MachinePlatformAccount();
        binding.setMachineId(8);
        binding.setAccountId(6);

        when(orderService.getById(43)).thenReturn(order);
        when(accountService.getById(6)).thenReturn(account);
        when(machinePlatformAccountService.findByAccountIdActive(6))
                .thenReturn(List.of(binding));
        when(agentRegistry.pickAgent(8)).thenReturn(8);
        when(platformService.getById(2)).thenReturn(itemBay());
        when(agentRegistry.sendChat(
                anyInt(), anyString(), anyInt(), anyInt(), anyInt(), anyString(),
                anyString(), anyString(), anyList(), anyMap()))
                .thenReturn(true);

        service.dispatchOrderChat(
                43,
                List.of(Map.of("type", "text", "content", "안녕하세요")));

        @SuppressWarnings("unchecked")
        ArgumentCaptor<Map<String, Object>> target =
                ArgumentCaptor.forClass(Map.class);
        verify(agentRegistry).sendChat(
                anyInt(), anyString(), anyInt(), anyInt(), anyInt(), anyString(),
                anyString(), anyString(), anyList(), target.capture());

        assertEquals(
                "https://www.itembay.com/ibmessenger/bayTalkChatTran"
                        + "?iTranSeq=96370042",
                target.getValue().get("url"));
        assertEquals("#txtAreaMsgSend", target.getValue().get("input_selector"));
        assertEquals("#btnSend", target.getValue().get("send_selector"));
        assertEquals("#txtScreenShot", target.getValue().get("file_selector"));
        assertEquals("#sTalkPop", target.getValue().get("blocking_popup_selector"));
        assertEquals(
                "#sTalkPop .btn_pop_close",
                target.getValue().get("blocking_popup_close_selector"));
        assertEquals(
                "#chat_container .list_message li.send",
                target.getValue().get("sent_selector"));
        assertEquals(true, target.getValue().get("upload_auto_send"));
        assertEquals(800, target.getValue().get("max_text_length"));
        assertEquals(5 * 1024 * 1024, target.getValue().get("max_image_bytes"));
    }

    @Test
    void barotemResolvesJangNumFromTheSellerOrderList() {
        GameItemOrder order = barotemOrder();
        PlatformAccount account = new PlatformAccount();
        account.setId(7);
        account.setWebsiteId(3);
        account.setIsActive(1);
        MachinePlatformAccount binding = new MachinePlatformAccount();
        binding.setMachineId(9);
        binding.setAccountId(7);

        when(orderService.getById(44)).thenReturn(order);
        when(accountService.getById(7)).thenReturn(account);
        when(machinePlatformAccountService.findByAccountIdActive(7))
                .thenReturn(List.of(binding));
        when(agentRegistry.pickAgent(9)).thenReturn(9);
        when(platformService.getById(3)).thenReturn(barotem());
        when(agentRegistry.sendChat(
                anyInt(), anyString(), anyInt(), anyInt(), anyInt(), anyString(),
                anyString(), anyString(), anyList(), anyMap()))
                .thenReturn(true);

        service.dispatchOrderChat(
                44,
                List.of(Map.of("type", "text", "content", "hello")));

        @SuppressWarnings("unchecked")
        ArgumentCaptor<Map<String, Object>> target =
                ArgumentCaptor.forClass(Map.class);
        verify(agentRegistry).sendChat(
                anyInt(), anyString(), anyInt(), anyInt(), anyInt(), anyString(),
                anyString(), anyString(), anyList(), target.capture());

        assertEquals(
                "barotem_order_list",
                target.getValue().get("conversation_resolver"));
        assertEquals(
                "178583752411285073-61",
                target.getValue().get("order_no"));
        assertTrue(target.getValue().get("url").toString().contains(
                "/mypage/sellview/4"));
        assertTrue(target.getValue().get("url").toString().contains(
                "itemtype=money"));
        assertEquals(
                "#happy_chating_form #message",
                target.getValue().get("input_selector"));
        assertEquals(
                "#happy_chating_form .chat_send_btn",
                target.getValue().get("send_selector"));
        assertEquals(
                "#chatBox .chattingDate.chat_converse.from_me",
                target.getValue().get("sent_selector"));
        assertEquals(true, target.getValue().get("barotem_image_submit"));
        assertEquals(
                false,
                target.getValue().containsKey("file_selector"));
        assertEquals(
                false,
                target.getValue().containsKey("upload_auto_send"));
        assertEquals(
                false,
                target.getValue().containsKey("upload_send_selector"));
    }

    @Test
    void finalConfirmationUsesGameRequestIdAndWaitsOnlyForNewBuyerReply() {
        GameItemOrder order = barotemOrder();
        PlatformAccount account = new PlatformAccount();
        account.setId(7);
        account.setWebsiteId(3);
        account.setIsActive(1);
        MachinePlatformAccount binding = new MachinePlatformAccount();
        binding.setMachineId(9);
        binding.setAccountId(7);

        when(orderService.getById(44)).thenReturn(order);
        when(accountService.getById(7)).thenReturn(account);
        when(machinePlatformAccountService.findByAccountIdActive(7))
                .thenReturn(List.of(binding));
        when(agentRegistry.pickAgent(9)).thenReturn(9);
        when(platformService.getById(3)).thenReturn(barotem());
        when(agentRegistry.sendChat(
                anyInt(), anyString(), anyInt(), anyInt(), anyInt(), anyString(),
                anyString(), anyString(), anyList(), anyMap()))
                .thenReturn(true);

        service.dispatchTradeFinalConfirmation(
                44,
                "game-request-1",
                List.of(
                        Map.of("content", "네라고 답해주세요"),
                        Map.of(
                                "type", "image",
                                "image_url", "/uploads/trade-screenshots/proof.png")));

        @SuppressWarnings("unchecked")
        ArgumentCaptor<Map<String, Object>> target =
                ArgumentCaptor.forClass(Map.class);
        verify(agentRegistry).sendChat(
                eq(9),
                eq("game-request-1"),
                eq(44),
                eq(3),
                eq(7),
                eq("barotem"),
                eq("178583752411285073-61"),
                eq(TradeFinalConfirmationService.PURPOSE),
                anyList(),
                target.capture());
        assertEquals(true, target.getValue().get("wait_for_reply"));
        assertEquals(
                "#chatBox .chattingDate.chat_converse",
                target.getValue().get("conversation_selector"));
        assertEquals(
                "from_me",
                target.getValue().get("conversation_self_class"));
        assertEquals(
                ".chat_txt",
                target.getValue().get("conversation_text_selector"));
        assertEquals(
                List.of(
                        "네",
                        "예",
                        "넵",
                        "네네",
                        "네 본인 맞습니다",
                        "네 본인 맛습니다",
                        "맛습니다",
                        "맞습니다",
                        "맞아요",
                        "본인입니다",
                        "ok",
                        "네 저예요"),
                target.getValue().get("affirmative_replies"));
        assertEquals(300_000, target.getValue().get("reply_timeout_ms"));
    }

    @Test
    void barotemDeliveryConfirmationUsesTheResolvedChatReceiptRequest() {
        GameItemOrder order = barotemOrder();
        order.setDeliveryStatus("wait_web_confirm");
        order.setStatus("processing");
        order.setGameTradeScreenshot(
                "/uploads/trade-screenshots/2026/08/06/barotem-proof.png");
        PlatformAccount account = new PlatformAccount();
        account.setId(7);
        account.setWebsiteId(3);
        account.setIsActive(1);
        MachinePlatformAccount binding = new MachinePlatformAccount();
        binding.setMachineId(9);
        binding.setAccountId(7);

        when(orderService.getById(44)).thenReturn(order);
        when(accountService.getById(7)).thenReturn(account);
        when(machinePlatformAccountService.findByAccountIdActive(7))
                .thenReturn(List.of(binding));
        when(agentRegistry.pickAgent(9)).thenReturn(9);
        when(platformService.getById(3)).thenReturn(barotem());
        when(agentRegistry.sendChat(
                anyInt(), anyString(), anyInt(), anyInt(), anyInt(), anyString(),
                anyString(), anyString(), anyList(), anyMap(), anyMap()))
                .thenReturn(true);

        service.dispatchDeliveryConfirmation(44);

        @SuppressWarnings("unchecked")
        ArgumentCaptor<Map<String, Object>> action =
                ArgumentCaptor.forClass(Map.class);
        verify(agentRegistry).sendChat(
                anyInt(), anyString(), anyInt(), anyInt(), anyInt(), anyString(),
                anyString(), anyString(), anyList(), anyMap(), action.capture());

        assertTrue(action.getValue().get("detail_url").toString().contains(
                "/mypage/sellview/4"));
        assertTrue(action.getValue().get("detail_url").toString().contains(
                "itemtype=money"));
        assertEquals(
                "barotem_order_list",
                action.getValue().get("conversation_resolver"));
        assertEquals(
                "178583752411285073-61",
                action.getValue().get("order_no"));
        assertEquals("#state5", action.getValue().get("open_confirm_selector"));
        assertEquals(
                "#commonAlert .common_alert_check",
                action.getValue().get("confirm_selector"));
        assertEquals(
                "#commonAlert .common_alert_wrap h2",
                action.getValue().get("success_selector"));
        assertEquals(
                List.of("구매자에게 인수확인 요청하였습니다."),
                action.getValue().get("success_texts"));
        assertEquals(
                ".chat_info_process > div",
                action.getValue().get("stage_selector"));
        assertEquals("on", action.getValue().get("stage_active_class"));
        assertEquals(2, action.getValue().get("pending_stage"));
        assertEquals(true, action.getValue().get("success_before_reload"));
    }

    @Test
    void itemBayDeliveryConfirmationUsesSellerOrderDetailPage() {
        GameItemOrder order = itemBayOrder();
        order.setDeliveryStatus("wait_web_confirm");
        order.setStatus("processing");
        order.setGameTradeScreenshot(
                "/uploads/trade-screenshots/2026/08/04/itembay-proof.png");
        PlatformAccount account = new PlatformAccount();
        account.setId(6);
        account.setWebsiteId(2);
        account.setIsActive(1);
        MachinePlatformAccount binding = new MachinePlatformAccount();
        binding.setMachineId(8);
        binding.setAccountId(6);

        when(orderService.getById(43)).thenReturn(order);
        when(accountService.getById(6)).thenReturn(account);
        when(machinePlatformAccountService.findByAccountIdActive(6))
                .thenReturn(List.of(binding));
        when(agentRegistry.pickAgent(8)).thenReturn(8);
        when(platformService.getById(2)).thenReturn(itemBay());
        when(agentRegistry.sendChat(
                anyInt(), anyString(), anyInt(), anyInt(), anyInt(), anyString(),
                anyString(), anyString(), anyList(), anyMap(), anyMap()))
                .thenReturn(true);

        service.dispatchDeliveryConfirmation(43);

        @SuppressWarnings("unchecked")
        ArgumentCaptor<Map<String, Object>> action =
                ArgumentCaptor.forClass(Map.class);
        verify(agentRegistry).sendChat(
                anyInt(), anyString(), anyInt(), anyInt(), anyInt(), anyString(),
                anyString(), anyString(), anyList(), anyMap(), action.capture());

        assertEquals(
                "https://www.itembay.com/item/transaction/"
                        + "transactionGiveTakeDetail?iTranSeq=96370042",
                action.getValue().get("detail_url"));
        assertEquals(
                ".bay-btn-confirm[onclick*='ItemGiveTake.setGiveItem']",
                action.getValue().get("open_confirm_selector"));
        assertEquals(true, action.getValue().get("single_click"));
        assertEquals(
                "#middle .list-page-detail",
                action.getValue().get("ready_selector"));
        assertEquals(
                action.getValue().get("open_confirm_selector"),
                action.getValue().get("success_absent_selector"));
        assertEquals(
                "/mybay/status/mybayStatusGiveList",
                action.getValue().get("success_url_contains"));
        assertEquals(false, action.getValue().containsKey("confirm_selector"));
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

    private GameItemOrder itemBayOrder() {
        GameItemOrder order = new GameItemOrder();
        order.setId(43);
        order.setWebsiteId(2);
        order.setPlatformAccountId(6);
        order.setSourceOrderNo("96370042");
        order.setDeliveryStatus("greeting");
        order.setStatus("pending");
        return order;
    }

    private Platform itemBay() {
        Platform platform = new Platform();
        platform.setId(2);
        platform.setName("ItemBay");
        platform.setUrl("https://www.itembay.com/login");
        platform.setIsActive(1);
        platform.setLoginConfig(Map.of());
        return platform;
    }

    private GameItemOrder barotemOrder() {
        GameItemOrder order = new GameItemOrder();
        order.setId(44);
        order.setWebsiteId(3);
        order.setPlatformAccountId(7);
        order.setSourceOrderNo("178583752411285073-61");
        order.setPlatformItemType("money");
        order.setDeliveryStatus("greeting");
        order.setStatus("pending");
        return order;
    }

    private Platform barotem() {
        Platform platform = new Platform();
        platform.setId(3);
        platform.setName("Barotem");
        platform.setUrl("https://www.barotem.com/login");
        platform.setIsActive(1);
        platform.setLoginConfig(Map.of());
        return platform;
    }
}
