package com.auto.controller;

import com.auto.common.PageRequests;
import com.auto.entity.Machine;
import com.auto.entity.SystemAlert;
import com.auto.entity.SystemAlertEvent;
import com.auto.service.MachineService;
import com.auto.service.SystemAlertService;
import com.baomidou.mybatisplus.core.metadata.IPage;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;

@RestController
@RequestMapping("/api/system-alerts")
public class SystemAlertController {

    private static final Set<String> CLIENT_EVENT_TYPES = Set.of(
            "presented", "voice_started", "voice_completed", "voice_failed");

    private final SystemAlertService alertService;
    private final MachineService machineService;

    public SystemAlertController(SystemAlertService alertService, MachineService machineService) {
        this.alertService = alertService;
        this.machineService = machineService;
    }

    @GetMapping
    public Map<String, Object> listOpen() {
        return alertResponse(alertService.listOpen());
    }

    @GetMapping("/history")
    public Map<String, Object> history(
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(name = "page_size", defaultValue = "50") int pageSize,
            @RequestParam(required = false) Integer limit,
            @RequestParam(required = false) String status,
            @RequestParam(name = "alert_type", required = false) String alertType,
            @RequestParam(required = false) String severity,
            @RequestParam(name = "machine_id", required = false) Integer machineId,
            @RequestParam(name = "account_id", required = false) Integer accountId,
            @RequestParam(required = false) String keyword) {
        if (limit != null) {
            page = 1;
            pageSize = PageRequests.limit(limit);
        }
        IPage<SystemAlert> result = alertService.searchHistory(
                status,
                alertType,
                severity,
                machineId,
                accountId,
                keyword,
                PageRequests.of(page, pageSize));
        return alertResponse(result);
    }

    @GetMapping("/{alertId}/events")
    public Map<String, Object> events(@PathVariable long alertId) {
        List<SystemAlertEvent> events = alertService.listEvents(alertId);
        List<Map<String, Object>> items = events.stream().map(event -> {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("id", event.getId());
            item.put("alert_id", event.getAlertId());
            item.put("event_type", event.getEventType());
            item.put("event_at", event.getEventAt());
            item.put("actor", event.getActor());
            item.put("details", event.getDetails());
            return item;
        }).toList();
        return Map.of("total", items.size(), "items", items);
    }

    @PostMapping("/{alertId}/events")
    public Map<String, Object> recordEvent(
            @PathVariable long alertId,
            @RequestBody AlertEventPayload payload) {
        if (payload == null || payload.eventType() == null
                || !CLIENT_EVENT_TYPES.contains(
                        payload.eventType().trim().toLowerCase())) {
            throw com.auto.common.ApiException.badRequest("不支持的告警通知事件");
        }
        alertService.recordClientEvent(
                alertId, payload.eventType(), payload.details());
        return Map.of("message", "告警通知事件已记录");
    }

    private Map<String, Object> alertResponse(List<SystemAlert> alerts) {
        List<Map<String, Object>> items = toAlertItems(alerts);
        Map<String, Object> response = new LinkedHashMap<>();
        response.put("total", items.size());
        response.put("items", items);
        response.put("polled_at", LocalDateTime.now());
        return response;
    }

    private Map<String, Object> alertResponse(IPage<SystemAlert> page) {
        List<Map<String, Object>> items = toAlertItems(page.getRecords());
        Map<String, Object> response = new LinkedHashMap<>();
        response.put("total", page.getTotal());
        response.put("items", items);
        response.put("page", page.getCurrent());
        response.put("page_size", page.getSize());
        response.put("polled_at", LocalDateTime.now());
        return response;
    }

    private List<Map<String, Object>> toAlertItems(List<SystemAlert> alerts) {
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
        return items;
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
        item.put("source_key", alert.getSourceKey());
        item.put("occurred_at", alert.getOccurredAt());
        item.put("last_occurred_at", alert.getLastOccurredAt());
        item.put("occurrence_count", alert.getOccurrenceCount());
        item.put("status", alert.getStatus());
        item.put("presentation_count", alert.getPresentationCount());
        item.put("last_presented_at", alert.getLastPresentedAt());
        item.put("voice_notification_count", alert.getVoiceNotificationCount());
        item.put("last_voice_notified_at", alert.getLastVoiceNotifiedAt());
        item.put("dismissed_at", alert.getDismissedAt());
        item.put("close_type", alert.getCloseType());
        item.put("close_reason", alert.getCloseReason());
        item.put("closed_by", alert.getClosedBy());
        item.put("created_at", alert.getCreatedAt());
        item.put("updated_at", alert.getUpdatedAt());
        return item;
    }

    public record AlertEventPayload(String eventType, String details) {
    }
}
