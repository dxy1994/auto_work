package com.auto.controller;

import com.auto.common.ApiException;
import com.auto.entity.Machine;
import com.auto.entity.MachinePlatformAccount;
import com.auto.entity.PlatformAccount;
import com.auto.service.MachineGameAccountService;
import com.auto.service.MachinePlatformAccountService;
import com.auto.service.MachineService;
import com.auto.service.MouseKeyboardDeviceService;
import com.auto.service.PlatformAccountService;
import com.auto.service.VideoStreamDeviceService;
import com.auto.ws.AgentRegistry;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class MachineControllerPlatformAccountTest {

    private MachineService machineService;
    private MachinePlatformAccountService bindingService;
    private PlatformAccountService accountService;
    private AgentRegistry agentRegistry;
    private MachineController controller;

    @BeforeEach
    void setUp() {
        machineService = mock(MachineService.class);
        bindingService = mock(MachinePlatformAccountService.class);
        accountService = mock(PlatformAccountService.class);
        agentRegistry = mock(AgentRegistry.class);
        controller = new MachineController(
                machineService,
                mock(MachineGameAccountService.class),
                bindingService,
                accountService,
                mock(MouseKeyboardDeviceService.class),
                mock(VideoStreamDeviceService.class),
                agentRegistry);
    }

    @Test
    void accountBoundToAnotherMachineCannotBeSelectedAgain() {
        Machine target = machine(1, "监控机 A");
        Machine owner = machine(2, "监控机 B");
        MachinePlatformAccount existing = binding(9, 2, 4);
        when(machineService.getById(1)).thenReturn(target);
        when(machineService.getById(2)).thenReturn(owner);
        when(accountService.getById(4)).thenReturn(account(4));
        when(bindingService.findByAccountIdActive(4)).thenReturn(List.of(existing));
        MachinePlatformAccount request = new MachinePlatformAccount();
        request.setAccountId(4);

        ApiException error = assertThrows(
                ApiException.class, () -> controller.addAccount(1, request));

        assertEquals(409, error.getStatus().value());
        assertTrue(error.getMessage().contains("监控机 B"));
        verify(bindingService, never()).save(request);
    }

    @Test
    void bindingListIncludesTheOwningMachineIdentity() {
        Machine owner = machine(2, "监控机 B");
        owner.setHostname("worker-b");
        owner.setMacAddress("AA:BB:CC:DD:EE:FF");
        when(bindingService.findAllActive()).thenReturn(List.of(binding(9, 2, 4)));
        when(machineService.getById(2)).thenReturn(owner);

        List<Map<String, Object>> result = controller.listAccountBindings();

        assertEquals(1, result.size());
        assertEquals(4, result.get(0).get("account_id"));
        assertEquals(2, result.get(0).get("machine_id"));
        assertEquals("监控机 B", result.get(0).get("machine_name"));
        assertEquals("worker-b", result.get(0).get("machine_hostname"));
    }

    @Test
    void unboundActiveAccountCanBeAssociated() {
        when(machineService.getById(1)).thenReturn(machine(1, "监控机 A"));
        when(accountService.getById(4)).thenReturn(account(4));
        when(bindingService.findByAccountIdActive(4)).thenReturn(List.of());
        MachinePlatformAccount request = new MachinePlatformAccount();
        request.setAccountId(4);

        MachinePlatformAccount result = controller.addAccount(1, request);

        assertEquals(1, result.getMachineId());
        assertEquals(1, result.getIsActive());
        verify(bindingService).save(request);
    }

    @Test
    void removingBindingImmediatelyStopsItsRunningMonitor() {
        MachinePlatformAccount existing = binding(9, 2, 4);
        AgentRegistry.TaskInfo running = new AgentRegistry.TaskInfo();
        running.machineId = 2;
        running.taskId = "order-4";
        running.status = "running";
        when(bindingService.getById(9)).thenReturn(existing);
        when(agentRegistry.getAccountTask(4)).thenReturn(running);

        controller.removeAccount(9);

        verify(bindingService).removeById(9);
        verify(agentRegistry).requestOrderCheckStop(
                2, 4, "账号已从该机器解绑，正在停止监控...");
    }

    private Machine machine(int id, String name) {
        Machine machine = new Machine();
        machine.setId(id);
        machine.setName(name);
        return machine;
    }

    private MachinePlatformAccount binding(int id, int machineId, int accountId) {
        MachinePlatformAccount binding = new MachinePlatformAccount();
        binding.setId(id);
        binding.setMachineId(machineId);
        binding.setAccountId(accountId);
        binding.setIsActive(1);
        return binding;
    }

    private PlatformAccount account(int id) {
        PlatformAccount account = new PlatformAccount();
        account.setId(id);
        account.setIsActive(1);
        return account;
    }
}
