package com.auto.ws;

import com.auto.entity.Machine;
import com.auto.service.MachineService;
import com.auto.trade.MachineSessionRestored;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.web.socket.WebSocketSession;
import tools.jackson.databind.ObjectMapper;

import java.net.InetSocketAddress;
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
    private AgentRegistry registry;

    @BeforeEach
    void setUp() {
        machineService = mock(MachineService.class);
        eventPublisher = mock(ApplicationEventPublisher.class);
        registry = new AgentRegistry(mock(ObjectMapper.class), machineService, eventPublisher);
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

    private Machine machine(int id, String status) {
        Machine machine = new Machine();
        machine.setId(id);
        machine.setStatus(status);
        machine.setIsActive(1);
        return machine;
    }
}
