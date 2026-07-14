package com.auto.trade;

import com.auto.entity.Machine;
import com.auto.service.MachineService;
import com.auto.ws.AgentRegistry;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class AgentRegistryRuntimeStatusTest {

    @Test
    void heartbeatStoresTypedRuntimeSnapshot() {
        MachineService machineService = mock(MachineService.class);
        Machine machine = new Machine();
        machine.setId(12);
        machine.setStatus("online");
        when(machineService.getById(12)).thenReturn(machine);
        AgentRegistry registry = new AgentRegistry(new ObjectMapper(), machineService);

        registry.updateHeartbeat(12, Map.of("runtime", Map.of(
                "game_id", 3,
                "game_account_id", 27,
                "region_id", 8,
                "client_status", "logged_in",
                "character_name", "테스터",
                "executor_status", "idle",
                "ui_health", "ready")));

        WorkerRuntimeStatus runtime = registry.getRuntimeStatus(12);
        assertThat(runtime.gameId()).isEqualTo(3);
        assertThat(runtime.gameAccountId()).isEqualTo(27);
        assertThat(runtime.executorStatus()).isEqualTo("idle");
        assertThat(runtime.uiHealth()).isEqualTo("ready");
        verify(machineService).updateById(machine);
    }
}
