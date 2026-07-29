package com.auto.ws;

import com.auto.entity.Machine;
import com.auto.service.MachineService;
import com.auto.service.WirelessHidDeviceManager;
import com.auto.service.WirelessHidDeviceManager.WorkerBinding;
import com.auto.trade.MachineSessionRestored;
import com.auto.trade.TradeOffer;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.web.socket.WebSocketSession;
import tools.jackson.databind.ObjectMapper;

import java.net.InetSocketAddress;
import java.time.Instant;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.argThat;
import static org.mockito.Mockito.*;

class AgentRegistryReconnectTest {

    private MachineService machineService;
    private ApplicationEventPublisher eventPublisher;
    private WirelessHidDeviceManager wirelessHidDeviceManager;
    private ObjectMapper objectMapper;
    private AgentRegistry registry;

    @BeforeEach
    void setUp() {
        machineService = mock(MachineService.class);
        eventPublisher = mock(ApplicationEventPublisher.class);
        wirelessHidDeviceManager = mock(WirelessHidDeviceManager.class);
        objectMapper = mock(ObjectMapper.class);
        registry = new AgentRegistry(
                objectMapper,
                machineService,
                eventPublisher,
                wirelessHidDeviceManager);
    }

    @Test
    void registerPublishesRestoredEventWhenExistingMachineWasOffline() {
        Machine machine = machine(7, "offline");
        when(machineService.findByMacAddress("AA:BB:CC:DD:EE:FF")).thenReturn(machine);

        Integer machineId = registry.handleRegister(Map.of(
                "mac", "AA:BB:CC:DD:EE:FF",
                "hostname", "worker-01",
                "ip", "127.0.0.1",
                "os", "Windows 11",
                "role", "game_executor"));

        assertEquals(7, machineId);
        assertEquals("online", machine.getStatus());
        verify(eventPublisher).publishEvent(argThat((Object event) ->
                event instanceof MachineSessionRestored restored
                        && restored.machineId() == 7));
    }

    @Test
    void registerAlsoClearsStaleAlertWhenPersistedMachineWasAlreadyOnline() {
        Machine machine = machine(7, "online");
        when(machineService.findByMacAddress("AA:BB:CC:DD:EE:FF")).thenReturn(machine);

        registry.handleRegister(Map.of("mac", "AA:BB:CC:DD:EE:FF"));

        verify(eventPublisher).publishEvent(argThat((Object event) ->
                event instanceof MachineSessionRestored restored
                        && restored.machineId() == 7));
    }

    @Test
    void firstHeartbeatAfterOfflineStatusPublishesRestoredEventOnlyOnce() {
        Machine machine = machine(7, "offline");
        when(machineService.getById(7)).thenReturn(machine);

        registry.updateHeartbeat(7);
        registry.updateHeartbeat(7);

        assertEquals("online", machine.getStatus());
        verify(eventPublisher, times(1)).publishEvent(argThat((Object event) ->
                event instanceof MachineSessionRestored restored
                        && restored.machineId() == 7));
    }

    @Test
    void heartbeatRefreshesTheMachinesReportedLanIp() {
        Machine machine = machine(7, "online");
        machine.setIpAddress("172.20.0.1");
        when(machineService.getById(7)).thenReturn(machine);

        registry.updateHeartbeat(7, Map.of("ip", "192.168.1.88"));

        assertEquals("192.168.1.88", machine.getIpAddress());
        verify(machineService).updateById(machine);
    }

    @Test
    @SuppressWarnings("unchecked")
    void sessionSnapshotContainsCurrentConnectionAndRuntimeState() {
        WebSocketSession session = mock(WebSocketSession.class);
        when(session.isOpen()).thenReturn(true);
        when(session.getId()).thenReturn("ws-7");
        when(session.getRemoteAddress()).thenReturn(new InetSocketAddress("127.0.0.1", 58231));
        registry.bindAgent(7, session);

        registry.updateHeartbeat(7, Map.of("runtime", Map.of(
                "role", "game_executor",
                "game_id", 2,
                "game_account_id", 11,
                "region_id", 5,
                "client_status", "logged_in",
                "character_name", "测试角色",
                "executor_status", "idle",
                "current_assignment_id", "assignment-9",
                "ui_health", "ready")));

        Map<String, Object> snapshot = registry.getSessionSnapshot(7);
        assertTrue((Boolean) snapshot.get("connected"));
        assertEquals("ws-7", snapshot.get("session_id"));
        assertEquals("game_executor", snapshot.get("role"));
        assertNotNull(snapshot.get("connected_at"));
        assertFalse(snapshot.containsKey("headers"));
        assertFalse(snapshot.containsKey("uri"));

        Map<String, Object> runtime = (Map<String, Object>) snapshot.get("runtime");
        assertEquals("logged_in", runtime.get("client_status"));
        assertEquals("ready", runtime.get("ui_health"));
        assertEquals("assignment-9", runtime.get("current_assignment_id"));
    }

    @Test
    void disconnectedSessionSnapshotClearsEphemeralSessionFields() {
        WebSocketSession session = mock(WebSocketSession.class);
        when(session.isOpen()).thenReturn(true);
        when(session.getId()).thenReturn("ws-7");
        registry.bindAgent(7, session);

        registry.onAgentDisconnect(7, session);

        Map<String, Object> snapshot = registry.getSessionSnapshot(7);
        assertFalse((Boolean) snapshot.get("connected"));
        assertNull(snapshot.get("session_id"));
        assertNull(snapshot.get("connected_at"));
        assertNull(snapshot.get("runtime"));
    }

    @Test
    void tradeOfferCarriesTheMachinesCurrentWirelessHidBinding() throws Exception {
        WebSocketSession session = mock(WebSocketSession.class);
        when(session.isOpen()).thenReturn(true);
        registry.bindAgent(7, session);
        when(wirelessHidDeviceManager.prepareWorkerBinding(7)).thenReturn(
                new WorkerBinding(
                        2,
                        "AABBCCDDEEFF",
                        "二号键鼠",
                        "192.168.1.32",
                        39667));
        when(objectMapper.writeValueAsString(argThat((Object value) -> {
            if (!(value instanceof Map<?, ?> payload)) {
                return false;
            }
            Object rawBinding = payload.get("wireless_hid");
            return rawBinding instanceof Map<?, ?> binding
                    && Integer.valueOf(2).equals(binding.get("record_id"))
                    && "AABBCCDDEEFF".equals(binding.get("device_id"));
        }))).thenReturn("{}");
        TradeOffer offer = new TradeOffer(
                "assignment-1",
                10,
                7,
                11,
                "token",
                Instant.now().plusSeconds(30),
                Map.of("game_code", "lineage_classic"));

        assertTrue(registry.sendTradeOffer(7, offer));
        verify(session).sendMessage(argThat(message -> "{}".equals(message.getPayload())));
    }

    @Test
    void tradeOfferIsNotSentBeforeMachineHasAKeyboardBinding() throws Exception {
        WebSocketSession session = mock(WebSocketSession.class);
        when(session.isOpen()).thenReturn(true);
        registry.bindAgent(7, session);
        when(wirelessHidDeviceManager.prepareWorkerBinding(7)).thenReturn(null);
        TradeOffer offer = new TradeOffer(
                "assignment-1",
                10,
                7,
                11,
                "token",
                Instant.now().plusSeconds(30),
                Map.of("game_code", "lineage_classic"));

        assertFalse(registry.sendTradeOffer(7, offer));
        verify(session, never()).sendMessage(any());
    }

    private Machine machine(int id, String status) {
        Machine machine = new Machine();
        machine.setId(id);
        machine.setStatus(status);
        machine.setIsActive(1);
        return machine;
    }
}
