package com.auto.trade;

import com.auto.entity.MachinePlatformAccount;
import com.auto.entity.Platform;
import com.auto.entity.PlatformAccount;
import com.auto.service.CryptoService;
import com.auto.service.MachinePlatformAccountService;
import com.auto.service.PlatformAccountService;
import com.auto.service.PlatformService;
import com.auto.ws.AgentRegistry;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class OrderMonitorAutoStartServiceTest {

    private MachinePlatformAccountService bindingService;
    private PlatformAccountService accountService;
    private PlatformService platformService;
    private CryptoService cryptoService;
    private AgentRegistry agentRegistry;
    private OrderMonitorAutoStartService service;

    @BeforeEach
    void setUp() {
        bindingService = mock(MachinePlatformAccountService.class);
        accountService = mock(PlatformAccountService.class);
        platformService = mock(PlatformService.class);
        cryptoService = mock(CryptoService.class);
        agentRegistry = mock(AgentRegistry.class);
        service = new OrderMonitorAutoStartService(
                bindingService, accountService, platformService, cryptoService, agentRegistry);
        when(agentRegistry.getMachineOrderTasks(7)).thenReturn(Map.of());
    }

    @Test
    void startsEveryActiveBoundAccountThatIsNotAlreadyRunning() {
        MachinePlatformAccount binding = binding(7, 4);
        PlatformAccount account = account(4, 3, 1);
        Platform platform = platform(3, 1);
        when(bindingService.findByMachineIdActive(7)).thenReturn(List.of(binding));
        when(accountService.getById(4)).thenReturn(account);
        when(platformService.getById(3)).thenReturn(platform);
        when(cryptoService.decrypt("encrypted")).thenReturn("plain-password");

        OrderMonitorAutoStartService.StartSummary summary = service.startBoundAccounts(7);

        assertEquals(1, summary.started());
        assertEquals(0, summary.alreadyRunning());
        verify(agentRegistry).dispatchOrderCheck(
                eq(7), anyString(), eq("https://example.com/login"), eq("seller"),
                eq("plain-password"), eq("form"), eq(Map.of("username_selector", "#id")),
                eq(3), eq(4));
    }

    @Test
    void restoredTaskIsNotDispatchedAgainOnReconnect() {
        MachinePlatformAccount binding = binding(7, 4);
        AgentRegistry.TaskInfo running = new AgentRegistry.TaskInfo();
        running.machineId = 7;
        running.taskId = "order-4";
        running.status = "running";
        when(bindingService.findByMachineIdActive(7)).thenReturn(List.of(binding));
        when(agentRegistry.getAccountTask(4)).thenReturn(running);

        OrderMonitorAutoStartService.StartSummary summary = service.startBoundAccounts(7);

        assertEquals(0, summary.started());
        assertEquals(1, summary.alreadyRunning());
        verify(agentRegistry, never()).dispatchOrderCheck(
                eq(7), anyString(), anyString(), anyString(), anyString(), anyString(),
                org.mockito.ArgumentMatchers.anyMap(), eq(3), eq(4));
    }

    @Test
    void inactiveAccountIsSkipped() {
        MachinePlatformAccount binding = binding(7, 4);
        when(bindingService.findByMachineIdActive(7)).thenReturn(List.of(binding));
        when(accountService.getById(4)).thenReturn(account(4, 3, 0));

        OrderMonitorAutoStartService.StartSummary summary = service.startBoundAccounts(7);

        assertEquals(1, summary.skipped());
        verify(platformService, never()).getById(3);
    }

    @Test
    void runningTaskForAnUnboundAccountIsStoppedDuringReconciliation() {
        AgentRegistry.TaskInfo stale = new AgentRegistry.TaskInfo();
        stale.machineId = 7;
        stale.taskId = "order-stale-4";
        stale.status = "running";
        when(bindingService.findByMachineIdActive(7)).thenReturn(List.of());
        when(agentRegistry.getMachineOrderTasks(7)).thenReturn(Map.of(4, stale));
        when(agentRegistry.requestOrderCheckStop(
                7, 4, "账号已从该机器解绑，正在停止监控..."))
                .thenReturn(true);

        OrderMonitorAutoStartService.StartSummary summary = service.startBoundAccounts(7);

        assertEquals(1, summary.stoppedUnbound());
        assertEquals(0, summary.started());
        verify(agentRegistry).requestOrderCheckStop(
                7, 4, "账号已从该机器解绑，正在停止监控...");
        verify(agentRegistry, never()).dispatchOrderCheck(
                eq(7), anyString(), anyString(), anyString(), anyString(), anyString(),
                org.mockito.ArgumentMatchers.anyMap(), eq(3), eq(4));
    }

    @Test
    void workerReportedUnboundTaskIsStoppedEvenWhenRegistryMirrorBelongsElsewhere() {
        when(bindingService.findByMachineIdActive(7)).thenReturn(List.of());
        when(agentRegistry.requestOrderCheckStop(
                7, 4, "账号已从该机器解绑，正在停止监控..."))
                .thenReturn(true);

        OrderMonitorAutoStartService.StartSummary summary = service.startBoundAccounts(
                7,
                List.of(Map.of(
                        "account_id", 4,
                        "task_id", "order-stale-4",
                        "status", "running")));

        assertEquals(1, summary.stoppedUnbound());
        verify(agentRegistry).requestOrderCheckStop(
                7, 4, "账号已从该机器解绑，正在停止监控...");
    }

    @Test
    void taskOnPreviousMachineIsStoppedBeforeStartingOnNewOwner() {
        MachinePlatformAccount binding = binding(7, 4);
        AgentRegistry.TaskInfo stale = new AgentRegistry.TaskInfo();
        stale.machineId = 8;
        stale.taskId = "order-old-machine";
        stale.status = "running";
        when(bindingService.findByMachineIdActive(7)).thenReturn(List.of(binding));
        when(agentRegistry.getAccountTask(4)).thenReturn(stale);
        when(agentRegistry.requestOrderCheckStop(
                8, 4, "账号已改绑其他机器，正在停止旧机器监控..."))
                .thenReturn(true);

        OrderMonitorAutoStartService.StartSummary summary = service.startBoundAccounts(7);

        assertEquals(1, summary.stoppedUnbound());
        assertEquals(0, summary.started());
        verify(agentRegistry).requestOrderCheckStop(
                8, 4, "账号已改绑其他机器，正在停止旧机器监控...");
    }

    private MachinePlatformAccount binding(int machineId, int accountId) {
        MachinePlatformAccount binding = new MachinePlatformAccount();
        binding.setMachineId(machineId);
        binding.setAccountId(accountId);
        binding.setIsActive(1);
        return binding;
    }

    private PlatformAccount account(int id, int websiteId, int active) {
        PlatformAccount account = new PlatformAccount();
        account.setId(id);
        account.setWebsiteId(websiteId);
        account.setUsername("seller");
        account.setPassword("encrypted");
        account.setIsActive(active);
        return account;
    }

    private Platform platform(int id, int active) {
        Platform platform = new Platform();
        platform.setId(id);
        platform.setUrl("https://example.com/login");
        platform.setLoginType("form");
        platform.setLoginConfig(Map.of("username_selector", "#id"));
        platform.setIsActive(active);
        return platform;
    }
}
