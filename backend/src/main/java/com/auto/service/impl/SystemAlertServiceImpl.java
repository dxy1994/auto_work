package com.auto.service.impl;

import com.auto.common.ApiException;
import com.auto.entity.SystemAlert;
import com.auto.entity.SystemAlertEvent;
import com.auto.mapper.SystemAlertMapper;
import com.auto.service.SystemAlertEventService;
import com.auto.service.SystemAlertService;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.spring.service.impl.ServiceImpl;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Set;

@Service
public class SystemAlertServiceImpl extends ServiceImpl<SystemAlertMapper, SystemAlert>
        implements SystemAlertService {

    private static final Set<String> CLIENT_EVENT_TYPES = Set.of(
            "presented", "voice_started", "voice_completed", "voice_failed");

    private final SystemAlertEventService eventService;

    public SystemAlertServiceImpl(SystemAlertEventService eventService) {
        this.eventService = eventService;
    }

    @Override
    public List<SystemAlert> listOpen() {
        return list(new LambdaQueryWrapper<SystemAlert>()
                .eq(SystemAlert::getStatus, "open")
                .orderByAsc(SystemAlert::getOccurredAt)
                .last("LIMIT 200"));
    }

    @Override
    public List<SystemAlert> listHistory(int limit) {
        int safeLimit = Math.max(1, Math.min(limit, 1000));
        return list(new LambdaQueryWrapper<SystemAlert>()
                .orderByDesc(SystemAlert::getOccurredAt)
                .orderByDesc(SystemAlert::getId)
                .last("LIMIT " + safeLimit));
    }

    @Override
    public IPage<SystemAlert> searchHistory(
            String status,
            String alertType,
            String severity,
            Integer machineId,
            Integer accountId,
            String keyword,
            Page<SystemAlert> page) {
        String normalizedStatus = normalizedFilter(status);
        String normalizedAlertType = normalizedFilter(alertType);
        String normalizedSeverity = normalizedFilter(severity);
        String normalizedKeyword = normalizedFilter(keyword);
        LambdaQueryWrapper<SystemAlert> query = new LambdaQueryWrapper<>();
        query.eq(normalizedStatus != null, SystemAlert::getStatus, normalizedStatus)
                .eq(normalizedAlertType != null, SystemAlert::getAlertType, normalizedAlertType)
                .eq(normalizedSeverity != null, SystemAlert::getSeverity, normalizedSeverity)
                .eq(machineId != null, SystemAlert::getMachineId, machineId)
                .eq(accountId != null, SystemAlert::getAccountId, accountId)
                .and(normalizedKeyword != null, item -> item
                        .like(SystemAlert::getTitle, normalizedKeyword)
                        .or().like(SystemAlert::getMessage, normalizedKeyword)
                        .or().like(SystemAlert::getSourceKey, normalizedKeyword)
                        .or().like(SystemAlert::getAlertType, normalizedKeyword))
                .orderByDesc(SystemAlert::getOccurredAt)
                .orderByDesc(SystemAlert::getId);
        return page(page, query);
    }

    @Override
    public List<SystemAlertEvent> listEvents(long alertId) {
        if (getById(alertId) == null) {
            throw ApiException.notFound("提醒不存在");
        }
        return eventService.list(
                new LambdaQueryWrapper<SystemAlertEvent>()
                        .eq(SystemAlertEvent::getAlertId, alertId)
                        .orderByAsc(SystemAlertEvent::getEventAt)
                        .orderByAsc(SystemAlertEvent::getId));
    }

    @Override
    @Transactional
    public SystemAlert openOrRefresh(String alertType, String sourceKey, Integer machineId,
                                     Integer accountId, String severity, String title, String message) {
        LocalDateTime now = LocalDateTime.now();
        SystemAlert alert = getOne(new LambdaQueryWrapper<SystemAlert>()
                .eq(SystemAlert::getSourceKey, sourceKey)
                .eq(SystemAlert::getStatus, "open")
                .orderByDesc(SystemAlert::getId)
                .last("LIMIT 1"), false);
        boolean created = alert == null;
        if (alert == null) {
            alert = new SystemAlert();
            alert.setAlertType(alertType);
            alert.setSourceKey(sourceKey);
            alert.setStatus("open");
            alert.setOccurrenceCount(1);
            alert.setOccurredAt(now);
            alert.setPresentationCount(0);
            alert.setVoiceNotificationCount(0);
            alert.setCreatedAt(now);
        } else {
            alert.setOccurrenceCount(valueOrZero(alert.getOccurrenceCount()) + 1);
        }
        alert.setMachineId(machineId);
        alert.setAccountId(accountId);
        alert.setSeverity(severity);
        alert.setTitle(title);
        alert.setMessage(message);
        alert.setStatus("open");
        alert.setLastOccurredAt(now);
        alert.setDismissedAt(null);
        alert.setCloseType(null);
        alert.setCloseReason(null);
        alert.setClosedBy(null);
        alert.setUpdatedAt(now);
        saveOrUpdate(alert);
        appendEvent(
                alert,
                created ? "opened" : "refreshed",
                now,
                "backend",
                created ? "系统产生告警" : "相同来源告警再次发生");
        return alert;
    }

    @Override
    @Transactional
    public SystemAlert dismiss(long alertId) {
        SystemAlert alert = getById(alertId);
        if (alert == null) {
            throw ApiException.notFound("提醒不存在");
        }
        return dismissAlert(
                alert,
                "manual_dismissed",
                "用户在中控关闭提醒",
                "control-ui");
    }

    @Override
    @Transactional
    public SystemAlert dismissBySourceKey(String sourceKey) {
        SystemAlert alert = getOne(new LambdaQueryWrapper<SystemAlert>()
                .eq(SystemAlert::getSourceKey, sourceKey)
                .eq(SystemAlert::getStatus, "open")
                .orderByDesc(SystemAlert::getId)
                .last("LIMIT 1"), false);
        if (alert == null) {
            return null;
        }
        return dismissAlert(
                alert,
                "auto_recovered",
                "系统检测到对应故障已恢复",
                "backend");
    }

    @Override
    @Transactional
    public void recordClientEvent(
            long alertId, String eventType, String details) {
        String normalizedType = eventType == null
                ? "" : eventType.trim().toLowerCase();
        if (!CLIENT_EVENT_TYPES.contains(normalizedType)) {
            throw ApiException.badRequest("不支持的告警通知事件: " + eventType);
        }
        SystemAlert alert = getById(alertId);
        if (alert == null) {
            throw ApiException.notFound("提醒不存在");
        }
        LocalDateTime now = LocalDateTime.now();
        if ("presented".equals(normalizedType)) {
            alert.setPresentationCount(valueOrZero(alert.getPresentationCount()) + 1);
            alert.setLastPresentedAt(now);
            alert.setUpdatedAt(now);
            updateById(alert);
        } else if ("voice_started".equals(normalizedType)) {
            alert.setVoiceNotificationCount(
                    valueOrZero(alert.getVoiceNotificationCount()) + 1);
            alert.setLastVoiceNotifiedAt(now);
            alert.setUpdatedAt(now);
            updateById(alert);
        }
        appendEvent(
                alert,
                normalizedType,
                now,
                "control-ui",
                boundedDetails(details));
    }

    private SystemAlert dismissAlert(
            SystemAlert alert,
            String closeType,
            String closeReason,
            String closedBy) {
        if (!"dismissed".equals(alert.getStatus())) {
            LocalDateTime now = LocalDateTime.now();
            alert.setStatus("dismissed");
            alert.setDismissedAt(now);
            alert.setCloseType(closeType);
            alert.setCloseReason(closeReason);
            alert.setClosedBy(closedBy);
            alert.setUpdatedAt(now);
            updateById(alert);
            appendEvent(
                    alert,
                    closeType,
                    now,
                    closedBy,
                    closeReason);
        }
        return alert;
    }

    private void appendEvent(
            SystemAlert alert,
            String eventType,
            LocalDateTime eventAt,
            String actor,
            String details) {
        SystemAlertEvent event = new SystemAlertEvent();
        event.setAlertId(alert.getId());
        event.setEventType(eventType);
        event.setEventAt(eventAt);
        event.setActor(actor);
        event.setDetails(boundedDetails(details));
        event.setCreatedAt(eventAt);
        eventService.save(event);
    }

    private static int valueOrZero(Integer value) {
        return value == null ? 0 : value;
    }

    private static String boundedDetails(String details) {
        if (details == null) {
            return null;
        }
        String normalized = details.trim();
        return normalized.length() <= 1000
                ? normalized : normalized.substring(0, 1000);
    }

    private static String normalizedFilter(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }
        return value.trim();
    }
}
