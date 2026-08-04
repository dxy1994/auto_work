package com.auto.trade;

import com.auto.entity.Machine;
import com.auto.entity.MachinePlatformAccount;
import com.auto.entity.PlatformAccount;
import com.auto.service.MachinePlatformAccountService;
import com.auto.service.MachineService;
import com.auto.service.PlatformAccountService;
import com.auto.service.SystemAlertService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

class SystemAlertEventListenerTest {

    private SystemAlertService alertService;
    private MachineService machineService;
    private PlatformAccountService accountService;
    private MachinePlatformAccountService associationService;
    private SystemAlertEventListener listener;

    @BeforeEach
    void setUp() {
        alertService = mock(SystemAlertService.class);
        machineService = mock(MachineService.class);
        accountService = mock(PlatformAccountService.class);
        associationService = mock(MachinePlatformAccountService.class);
        listener = new SystemAlertEventListener(
                alertService, machineService, accountService, associationService);
    }

    @Test
    void machineDisconnectCreatesPersistentManualAlert() {
        Machine machine = new Machine();
        machine.setId(7);
        machine.setName("监控主机 A");
        machine.setHostname("worker-a");
        machine.setMacAddress("AA:BB:CC:DD:EE:07");
        machine.setIpAddress("192.168.1.27");
        machine.setStatus("offline");
        when(machineService.getById(7)).thenReturn(machine);
        when(associationService.findByMachineIdActive(7))
                .thenReturn(List.of(new MachinePlatformAccount()));

        listener.onMachineSessionLost(new MachineSessionLost(7, "worker 断线"));

        verify(alertService).openOrRefresh(
                eq("machine_offline"), eq("machine:7:offline"), eq(7), isNull(),
                eq("critical"), eq("订单监控机器「监控主机 A」已掉线"),
                argThat(message -> message.contains("名称 监控主机 A")
                        && message.contains("主机名 worker-a")
                        && message.contains("MAC AA:BB:CC:DD:EE:07")
                        && message.contains("IP 192.168.1.27")
                        && message.contains("ID #7")
                        && message.contains("原因：worker 断线")
                        && message.contains("解决方案：")
                        && message.contains("自动移除")));
    }

    @Test
    void replacedOldSessionDoesNotAlertWhenMachineIsAlreadyOnline() {
        Machine machine = new Machine();
        machine.setId(7);
        machine.setStatus("online");
        when(machineService.getById(7)).thenReturn(machine);

        listener.onMachineSessionLost(new MachineSessionLost(7, "worker 连接已被新会话替换"));

        verifyNoInteractions(alertService);
    }

    @Test
    void machineReconnectAutomaticallyDismissesOfflineAlert() {
        listener.onMachineSessionRestored(new MachineSessionRestored(7));

        verify(alertService).dismissBySourceKey("machine:7:offline");
    }

    @Test
    void unexpectedMonitorStopCreatesAccountAlert() {
        Machine machine = new Machine();
        machine.setId(7);
        machine.setHostname("monitor-01");
        PlatformAccount account = new PlatformAccount();
        account.setId(12);
        account.setUsername("seller@example.com");
        when(machineService.getById(7)).thenReturn(machine);
        when(accountService.getById(12)).thenReturn(account);

        listener.onOrderMonitorStopped(new OrderMonitorStopped(
                7, 12, "task-1", "failed", "页面结构异常"));

        verify(alertService).openOrRefresh(
                eq("order_monitor_stopped"), eq("monitor:12:stopped"), eq(7), eq(12),
                eq("danger"), eq("订单监控已掉线"),
                argThat(message -> message.contains("页面结构异常")
                        && message.contains("重新启动订单监控")
                        && message.contains("自动移除")));
    }

    @Test
    void restoredOrderMonitorAutomaticallyDismissesAccountAlert() {
        listener.onOrderMonitorRestored(new OrderMonitorRestored(
                7, 12, "order-12-new"));

        verify(alertService).dismissBySourceKey("monitor:12:stopped");
    }
}
