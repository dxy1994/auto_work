package com.auto.controller;

import com.auto.entity.Machine;
import com.auto.entity.SystemAlert;
import com.auto.service.MachineService;
import com.auto.service.SystemAlertService;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import org.junit.jupiter.api.Test;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.any;
import static org.mockito.Mockito.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class SystemAlertControllerTest {

    @Test
    void listOpenIncludesMachineIdentityFields() {
        SystemAlertService alertService = mock(SystemAlertService.class);
        MachineService machineService = mock(MachineService.class);
        SystemAlertController controller = new SystemAlertController(alertService, machineService);

        SystemAlert alert = new SystemAlert();
        alert.setId(31L);
        alert.setAlertType("machine_offline");
        alert.setMachineId(7);
        alert.setSeverity("critical");
        alert.setTitle("订单监控机器「监控主机 A」已掉线");
        alert.setMessage("worker 断线");
        alert.setOccurredAt(LocalDateTime.of(2026, 8, 4, 10, 20));
        alert.setLastOccurredAt(LocalDateTime.of(2026, 8, 4, 10, 21));
        alert.setOccurrenceCount(2);
        alert.setPresentationCount(1);
        alert.setVoiceNotificationCount(3);
        when(alertService.listOpen()).thenReturn(List.of(alert));

        Machine machine = new Machine();
        machine.setId(7);
        machine.setName("监控主机 A");
        machine.setHostname("worker-a");
        machine.setMacAddress("AA:BB:CC:DD:EE:07");
        machine.setIpAddress("192.168.1.27");
        when(machineService.listByIds(List.of(7))).thenReturn(List.of(machine));

        Map<String, Object> response = controller.listOpen();
        @SuppressWarnings("unchecked")
        Map<String, Object> item = ((List<Map<String, Object>>) response.get("items")).get(0);

        assertEquals("监控主机 A", item.get("machine_name"));
        assertEquals("worker-a", item.get("machine_hostname"));
        assertEquals("AA:BB:CC:DD:EE:07", item.get("machine_mac_address"));
        assertEquals("192.168.1.27", item.get("machine_ip_address"));
        assertEquals(7, item.get("machine_id"));
        assertEquals(2, item.get("occurrence_count"));
        assertEquals(1, item.get("presentation_count"));
        assertEquals(3, item.get("voice_notification_count"));
    }

    @Test
    void frontendCanReportVoiceLifecycleEvent() {
        SystemAlertService alertService = mock(SystemAlertService.class);
        MachineService machineService = mock(MachineService.class);
        SystemAlertController controller =
                new SystemAlertController(alertService, machineService);

        Map<String, Object> response = controller.recordEvent(
                31L,
                new SystemAlertController.AlertEventPayload(
                        "voice_completed", "播报完成"));

        verify(alertService).recordClientEvent(
                31L, "voice_completed", "播报完成");
        assertEquals("告警通知事件已记录", response.get("message"));
    }

    @Test
    void historyReturnsDatabaseTotalPagingAndAuditIdentity() {
        SystemAlertService alertService = mock(SystemAlertService.class);
        MachineService machineService = mock(MachineService.class);
        SystemAlertController controller =
                new SystemAlertController(alertService, machineService);

        SystemAlert alert = new SystemAlert();
        alert.setId(31L);
        alert.setAlertType("machine_offline");
        alert.setSourceKey("machine:7:offline");
        alert.setMachineId(7);
        alert.setStatus("dismissed");
        alert.setOccurredAt(LocalDateTime.of(2026, 8, 4, 10, 20));
        Page<SystemAlert> result = Page.of(2, 20, 91);
        result.setRecords(List.of(alert));
        when(alertService.searchHistory(
                eq("dismissed"),
                eq("machine_offline"),
                eq("critical"),
                eq(7),
                eq(4),
                eq("offline"),
                any(Page.class))).thenReturn(result);

        Map<String, Object> response = controller.history(
                2, 20, null, "dismissed", "machine_offline", "critical",
                7, 4, "offline");
        @SuppressWarnings("unchecked")
        Map<String, Object> item =
                ((List<Map<String, Object>>) response.get("items")).get(0);

        assertEquals(91L, response.get("total"));
        assertEquals(2L, response.get("page"));
        assertEquals(20L, response.get("page_size"));
        assertEquals("machine:7:offline", item.get("source_key"));
    }
}
