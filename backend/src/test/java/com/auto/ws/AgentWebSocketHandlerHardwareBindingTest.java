package com.auto.ws;

import com.auto.service.WirelessHidDeviceManager;
import com.auto.service.WirelessHidDeviceManager.WorkerBinding;
import com.auto.trade.GreetingDispatchService;
import com.auto.trade.ChatDispatchService;
import com.auto.trade.MarketplaceOrderIngestionService;
import com.auto.trade.TradeDispatchCoordinator;
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
    private AgentWebSocketHandler handler;
    private WebSocketSession session;

    @BeforeEach
    void setUp() {
        registry = mock(AgentRegistry.class);
        wirelessHidDeviceManager = mock(WirelessHidDeviceManager.class);
        objectMapper = new ObjectMapper();
        handler = new AgentWebSocketHandler(
                registry,
                objectMapper,
                mock(TradeDispatchCoordinator.class),
                mock(MarketplaceOrderIngestionService.class),
                mock(GreetingDispatchService.class),
                mock(ChatDispatchService.class),
                wirelessHidDeviceManager);
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
}
