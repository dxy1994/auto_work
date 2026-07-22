package com.auto.controller;

import com.auto.entity.SystemAlert;
import com.auto.service.SystemAlertService;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/system-alerts")
public class SystemAlertController {

    private final SystemAlertService alertService;

    public SystemAlertController(SystemAlertService alertService) {
        this.alertService = alertService;
    }

    @GetMapping
    public Map<String, Object> listOpen() {
        List<Map<String, Object>> items = alertService.listOpen().stream()
                .map(this::toAlertMap)
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

    private Map<String, Object> toAlertMap(SystemAlert alert) {
        Map<String, Object> item = new LinkedHashMap<>();
        item.put("id", "system:" + alert.getId());
        item.put("alert_id", alert.getId());
        item.put("entity_type", "system");
        item.put("entity_id", alert.getMachineId() != null ? alert.getMachineId() : alert.getAccountId());
        item.put("machine_id", alert.getMachineId());
        item.put("account_id", alert.getAccountId());
        item.put("severity", alert.getSeverity());
        item.put("title", alert.getTitle());
        item.put("message", alert.getMessage());
        item.put("error_code", alert.getAlertType());
        item.put("occurred_at", alert.getOccurredAt());
        return item;
    }
}
