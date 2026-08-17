package com.auto.ws;

import com.auto.service.WirelessHidDeviceManager;
import com.auto.service.WirelessHidDeviceManager.WorkerBinding;
import com.auto.trade.GreetingDispatchService;
import com.auto.trade.ChatDispatchService;
import com.auto.trade.DeliveryConfirmationService;
import com.auto.trade.MarketplaceOrderIngestionService;
import com.auto.trade.OrderMonitorAutoStartService;
import com.auto.trade.TradeDispatchCoordinator;
import com.auto.trade.GameClientDisconnected;
import com.auto.trade.PlatformLoginVerificationChanged;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.web.socket.TextMessage;
import org.springframework.web.socket.WebSocketSession;
import tools.jackson.databind.ObjectMapper;

import java.util.HashMap;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class AgentWebSocketHandlerHardwareBindingTest {

    private AgentRegistry registry;
    private WirelessHidDeviceManager wirelessHidDeviceManager;
    private ObjectMapper objectMapper;
    private OrderMonitorAutoStartService orderMonitorAutoStartService;
    private AgentWebSocketHandler handler;
    private WebSocketSession session;

    @BeforeEach
    void setUp() {
        registry = mock(AgentRegistry.class);
        wirelessHidDeviceManager = mock(WirelessHidDeviceManager.class);
        orderMonitorAutoStartService = mock(OrderMonitorAutoStartService.class);
        objectMapper = new ObjectMapper();
        handler = new AgentWebSocketHandler(
                registry,
                objectMapper,
                mock(TradeDispatchCoordinator.class),
                mock(MarketplaceOrderIngestionService.class),
                mock(com.auto.trade.MarketplaceSalesProductSyncService.class),
                mock(GreetingDispatchService.class),
                mock(ChatDispatchService.class),
                mock(DeliveryConfirmationService.class),
                mock(com.auto.trade.TradeFinalConfirmationService.class),
                wirelessHidDeviceManager,
                orderMonitorAutoStartService);
        session = mock(WebSocketSession.class);
        when(session.getAttributes()).thenReturn(new HashMap<>());
    }

    @Test
    @SuppressWarnings("unchecked")
    void initialRegistrationCanSucceedWhileHardwareBindingIsStillMissing() throws Exception {
        when(registry.handleRegister(org.mockito.ArgumentMatchers.anyMap())).thenReturn(7);
        when(wirelessHidDeviceManager.prepareWorkerBinding(7)).thenReturn(null);

        handler.handleTextMessage(session, new TextMessage("""
                {"type":"register","role":"game_executor","mac":"AA:BB:CC:DD:EE:FF"}
                """));

        ArgumentCaptor<TextMessage> response = ArgumentCaptor.forClass(TextMessage.class);
        verify(session).sendMessage(response.capture());
        Map<String, Object> payload =
                objectMapper.readValue(response.getValue().getPayload(), Map.class);
        assertEquals("registered", payload.get("type"));
        assertEquals(7, ((Number) payload.get("machine_id")).intValue());
        assertNull(payload.get("wireless_hid"));
        assertTrue(payload.get("hardware_error").toString().contains("尚未绑定"));
    }

    @Test
    @SuppressWarnings("unchecked")
    void pollingReturnsBindingAsSoonAsMachineIsAssignedADevice() throws Exception {
        session.getAttributes().put("machineId", 7);
        when(wirelessHidDeviceManager.prepareWorkerBinding(7)).thenReturn(
                new WorkerBinding(
                        2,
                        "AABBCCDDEEFF",
                        "二号键鼠",
                        "192.168.1.32",
                        39667));

        handler.handleTextMessage(
                session,
                new TextMessage("{\"type\":\"hardware_binding_request\"}"));

        ArgumentCaptor<TextMessage> response = ArgumentCaptor.forClass(TextMessage.class);
        verify(session).sendMessage(response.capture());
        Map<String, Object> payload =
                objectMapper.readValue(response.getValue().getPayload(), Map.class);
        Map<String, Object> binding =
                (Map<String, Object>) payload.get("wireless_hid");
        assertEquals("hardware_binding", payload.get("type"));
        assertEquals(2, ((Number) binding.get("record_id")).intValue());
        assertEquals("AABBCCDDEEFF", binding.get("device_id"));
        assertEquals("192.168.1.32", binding.get("ip"));
    }

    @Test
    void monitorRegistrationRestoresTasksBeforeStartingMissingBindings() throws Exception {
        when(registry.handleRegister(org.mockito.ArgumentMatchers.anyMap())).thenReturn(7);

        handler.handleTextMessage(session, new TextMessage("""
                {"type":"register","role":"monitor","mac":"AA:BB:CC:DD:EE:FF",
                 "active_tasks":[{"account_id":4,"task_id":"order-4","status":"running"}]}
                """));

        verify(registry).restoreMonitorTasks(
                org.mockito.ArgumentMatchers.eq(7),
                org.mockito.ArgumentMatchers.argThat(value -> value instanceof java.util.List<?> list
                        && list.size() == 1));
        verify(orderMonitorAutoStartService).startBoundAccounts(
                org.mockito.ArgumentMatchers.eq(7),
                org.mockito.ArgumentMatchers.argThat(value -> value instanceof java.util.List<?> list
                        && list.size() == 1));
    }

    @Test
    void monitorHeartbeatContinuouslyReconcilesBindingsAndActualTasks() throws Exception {
        session.getAttributes().put("machineId", 7);

        handler.handleTextMessage(session, new TextMessage("""
                {"type":"heartbeat","runtime":{"role":"monitor","active_tasks":[]}}
                """));

        verify(registry).updateHeartbeat(
                org.mockito.ArgumentMatchers.eq(7),
                org.mockito.ArgumentMatchers.anyMap());
        verify(orderMonitorAutoStartService).startBoundAccounts(
                org.mockito.ArgumentMatchers.eq(7),
                org.mockito.ArgumentMatchers.argThat(value -> value instanceof java.util.List<?> list
                        && list.isEmpty()));
    }

    @Test
    void currentGameExecutorSessionPublishesDisconnectedClientEvent() throws Exception {
        session.getAttributes().put("machineId", 7);
        when(registry.isCurrentSession(7, session)).thenReturn(true);

        handler.handleTextMessage(session, new TextMessage("""
                {"type":"game_client_disconnected",
                 "game_code":"lineage_classic","game_name":"天堂经典版",
                 "account":"lineage@example.com","game_account_id":19,
                 "process_id":4321,"confidence":0.973,
                 "reason":"server_connection_lost_dialog"}
                """));

        ArgumentCaptor<GameClientDisconnected> event =
                ArgumentCaptor.forClass(GameClientDisconnected.class);
        verify(registry).publishGameClientDisconnected(event.capture());
        assertEquals(7, event.getValue().machineId());
        assertEquals("lineage_classic", event.getValue().gameCode());
        assertEquals("lineage@example.com", event.getValue().account());
        assertEquals(19, event.getValue().gameAccountId());
        assertEquals(4321, event.getValue().processId());
        assertEquals(0.973, event.getValue().confidence());
    }

    @Test
    void currentMonitorSessionPublishesLoginVerificationEvent() throws Exception {
        session.getAttributes().put("machineId", 7);
        when(registry.isCurrentSession(7, session)).thenReturn(true);

        handler.handleTextMessage(session, new TextMessage("""
                {"type":"platform_login_verification",
                 "account_id":12,"platform":"barotem",
                 "status":"required",
                 "reason":"Google 验证码需要人工完成"}
                """));

        ArgumentCaptor<PlatformLoginVerificationChanged> event =
                ArgumentCaptor.forClass(PlatformLoginVerificationChanged.class);
        verify(registry).publishPlatformLoginVerification(event.capture());
        assertEquals(7, event.getValue().machineId());
        assertEquals(12, event.getValue().accountId());
        assertEquals("barotem", event.getValue().platform());
        assertEquals("required", event.getValue().status());
        assertEquals("Google 验证码需要人工完成", event.getValue().reason());
    }

}
