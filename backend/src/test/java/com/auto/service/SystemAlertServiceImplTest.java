package com.auto.service;

import com.auto.entity.SystemAlert;
import com.auto.entity.SystemAlertEvent;
import com.auto.service.impl.SystemAlertServiceImpl;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

import java.time.LocalDateTime;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.doAnswer;
import static org.mockito.Mockito.doReturn;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.spy;
import static org.mockito.Mockito.verify;

class SystemAlertServiceImplTest {

    private SystemAlertEventService eventService;
    private SystemAlertServiceImpl service;

    @BeforeEach
    void setUp() {
        eventService = mock(SystemAlertEventService.class);
        service = spy(new SystemAlertServiceImpl(eventService));
    }

    @Test
    @SuppressWarnings("unchecked")
    void newIncidentCreatesLifecycleRowAndOpenedAuditEvent() {
        doReturn(null).when(service).getOne(
                any(LambdaQueryWrapper.class), eq(false));
        doAnswer(invocation -> {
            SystemAlert alert = invocation.getArgument(0);
            alert.setId(41L);
            return true;
        }).when(service).saveOrUpdate(any(SystemAlert.class));

        SystemAlert alert = service.openOrRefresh(
                "machine_offline",
                "machine:7:offline",
                7,
                null,
                "critical",
                "机器已掉线",
                "连接断开");

        assertEquals(41L, alert.getId());
        assertEquals("open", alert.getStatus());
        assertEquals(1, alert.getOccurrenceCount());
        assertNotNull(alert.getOccurredAt());
        assertEquals(alert.getOccurredAt(), alert.getLastOccurredAt());

        ArgumentCaptor<SystemAlertEvent> event =
                ArgumentCaptor.forClass(SystemAlertEvent.class);
        verify(eventService).save(event.capture());
        assertEquals(41L, event.getValue().getAlertId());
        assertEquals("opened", event.getValue().getEventType());
        assertEquals("backend", event.getValue().getActor());
    }

    @Test
    @SuppressWarnings("unchecked")
    void repeatedOpenAlertKeepsFirstTimeAndIncrementsOccurrenceCount() {
        SystemAlert existing = openAlert(41L);
        LocalDateTime firstOccurredAt = LocalDateTime.of(2026, 8, 6, 10, 0);
        existing.setOccurredAt(firstOccurredAt);
        existing.setLastOccurredAt(firstOccurredAt);
        existing.setOccurrenceCount(2);
        doReturn(existing).when(service).getOne(
                any(LambdaQueryWrapper.class), eq(false));
        doReturn(true).when(service).saveOrUpdate(existing);

        SystemAlert refreshed = service.openOrRefresh(
                "machine_offline",
                "machine:7:offline",
                7,
                null,
                "critical",
                "机器已掉线",
                "再次断开");

        assertEquals(firstOccurredAt, refreshed.getOccurredAt());
        assertTrue(refreshed.getLastOccurredAt().isAfter(firstOccurredAt));
        assertEquals(3, refreshed.getOccurrenceCount());

        ArgumentCaptor<SystemAlertEvent> event =
                ArgumentCaptor.forClass(SystemAlertEvent.class);
        verify(eventService).save(event.capture());
        assertEquals("refreshed", event.getValue().getEventType());
    }

    @Test
    void manualDismissRecordsWhoClosedTheAlert() {
        SystemAlert alert = openAlert(41L);
        doReturn(alert).when(service).getById(41L);
        doReturn(true).when(service).updateById(alert);

        SystemAlert dismissed = service.dismiss(41L);

        assertEquals("dismissed", dismissed.getStatus());
        assertEquals("manual_dismissed", dismissed.getCloseType());
        assertEquals("control-ui", dismissed.getClosedBy());
        assertNotNull(dismissed.getDismissedAt());

        ArgumentCaptor<SystemAlertEvent> event =
                ArgumentCaptor.forClass(SystemAlertEvent.class);
        verify(eventService).save(event.capture());
        assertEquals("manual_dismissed", event.getValue().getEventType());
    }

    @Test
    @SuppressWarnings("unchecked")
    void automaticRecoveryOnlyClosesTheCurrentOpenIncident() {
        SystemAlert alert = openAlert(41L);
        doReturn(alert).when(service).getOne(
                any(LambdaQueryWrapper.class), eq(false));
        doReturn(true).when(service).updateById(alert);

        SystemAlert dismissed = service.dismissBySourceKey(
                "machine:7:offline");

        assertEquals("auto_recovered", dismissed.getCloseType());
        assertEquals("backend", dismissed.getClosedBy());

        ArgumentCaptor<SystemAlertEvent> event =
                ArgumentCaptor.forClass(SystemAlertEvent.class);
        verify(eventService).save(event.capture());
        assertEquals("auto_recovered", event.getValue().getEventType());
    }

    @Test
    void frontendPresentationAndVoiceAreCountedAndAudited() {
        SystemAlert alert = openAlert(41L);
        alert.setPresentationCount(0);
        alert.setVoiceNotificationCount(0);
        doReturn(alert).when(service).getById(41L);
        doReturn(true).when(service).updateById(alert);

        service.recordClientEvent(41L, "presented", "已展示");
        service.recordClientEvent(41L, "voice_started", "开始播报");
        service.recordClientEvent(41L, "voice_completed", "播报完成");

        assertEquals(1, alert.getPresentationCount());
        assertNotNull(alert.getLastPresentedAt());
        assertEquals(1, alert.getVoiceNotificationCount());
        assertNotNull(alert.getLastVoiceNotifiedAt());
        verify(service, org.mockito.Mockito.times(2)).updateById(alert);

        ArgumentCaptor<SystemAlertEvent> events =
                ArgumentCaptor.forClass(SystemAlertEvent.class);
        verify(eventService, org.mockito.Mockito.times(3)).save(events.capture());
        assertEquals(
                java.util.List.of("presented", "voice_started", "voice_completed"),
                events.getAllValues().stream()
                        .map(SystemAlertEvent::getEventType)
                        .toList());
    }

    @Test
    void dismissingAlreadyClosedAlertDoesNotDuplicateAuditEvent() {
        SystemAlert alert = openAlert(41L);
        alert.setStatus("dismissed");
        alert.setCloseType("manual_dismissed");
        doReturn(alert).when(service).getById(41L);

        SystemAlert result = service.dismiss(41L);

        assertEquals("manual_dismissed", result.getCloseType());
        verify(service, never()).updateById(any(SystemAlert.class));
        verify(eventService, never()).save(any(SystemAlertEvent.class));
    }

    private static SystemAlert openAlert(long id) {
        SystemAlert alert = new SystemAlert();
        alert.setId(id);
        alert.setAlertType("machine_offline");
        alert.setSourceKey("machine:7:offline");
        alert.setStatus("open");
        alert.setOccurrenceCount(1);
        alert.setOccurredAt(LocalDateTime.now().minusMinutes(1));
        alert.setLastOccurredAt(alert.getOccurredAt());
        alert.setPresentationCount(0);
        alert.setVoiceNotificationCount(0);
        assertNull(alert.getDismissedAt());
        return alert;
    }
}
