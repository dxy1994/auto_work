package com.auto.controller;

import com.auto.entity.Machine;
import com.auto.entity.SystemAlert;
import com.auto.service.MachineService;
import com.auto.service.SystemAlertService;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;

@RestController
@RequestMapping("/api/system-alerts")
public class SystemAlertController {

    private final SystemAlertService alertService;
    private final MachineService machineService;

    public SystemAlertController(SystemAlertService alertService, MachineService machineService) {
        this.alertService = alertService;
        this.machineService = machineService;
    }

    @GetMapping
    public Map<String, Object> listOpen() {
        List<SystemAlert> alerts = alertService.listOpen();
        List<Integer> machineIds = alerts.stream()
                .map(SystemAlert::getMachineId)
                .filter(Objects::nonNull)
                .distinct()
                .toList();
        Map<Integer, Machine> machinesById = new HashMap<>();
        if (!machineIds.isEmpty()) {
            machineService.listByIds(machineIds)
                    .forEach(machine -> machinesById.put(machine.getId(), machine));
        }
        List<Map<String, Object>> items = alerts.stream()
                .map(alert -> toAlertMap(alert, machinesById.get(alert.getMachineId())))
                .toList();
        Map<String, Object> response = new LinkedHashMap<>();
        response.put("total", items.size());
        response.put("items", items);
        response.put("polled_at", LocalDateTime.now());
        return response;
    }

    @PostMapping("/{alertId}/dismiss")
    public Map<String, Object> dismiss(@PathVariable long alertId) {
        alertService.dismiss(alertId);
        return Map.of("message", "提醒已关闭");
    }

    private Map<String, Object> toAlertMap(SystemAlert alert, Machine machine) {
        Map<String, Object> item = new LinkedHashMap<>();
        item.put("id", "system:" + alert.getId());
        item.put("alert_id", alert.getId());
        item.put("entity_type", "system");
        item.put("entity_id", alert.getMachineId() != null ? alert.getMachineId() : alert.getAccountId());
        item.put("machine_id", alert.getMachineId());
        item.put("machine_name", machine == null ? null : machine.getName());
        item.put("machine_hostname", machine == null ? null : machine.getHostname());
        item.put("machine_mac_address", machine == null ? null : machine.getMacAddress());
        item.put("machine_ip_address", machine == null ? null : machine.getIpAddress());
        item.put("account_id", alert.getAccountId());
        item.put("severity", alert.getSeverity());
        item.put("title", alert.getTitle());
        item.put("message", alert.getMessage());
        item.put("error_code", alert.getAlertType());
        item.put("occurred_at", alert.getOccurredAt());
        return item;
    }
}
