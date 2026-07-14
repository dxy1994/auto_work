package com.auto.ws;

import com.auto.service.MachineService;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.web.socket.WebSocketSession;

import java.util.Map;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.doAnswer;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class AgentRegistryTest {

    private MachineService machineService;
    private AgentRegistry registry;

    @BeforeEach
    void setUp() {
        machineService = mock(MachineService.class);
        registry = new AgentRegistry(new ObjectMapper(), machineService);
    }

    @Test
    void dispatchLoginRejectsDuplicateTaskIdWithoutOverwritingOriginal() throws Exception {
        WebSocketSession session = openSession();
        registry.bindAgent(1, session);

        var original = registry.dispatchLogin(1, "same-task", false, "https://example.test",
                "user", "password", "form", Map.of(), 1, 10);

        assertThrows(IllegalStateException.class, () -> registry.dispatchLogin(1, "same-task", false,
                "https://example.test", "user", "password", "form", Map.of(), 1, 10));

        registry.handleTaskResult(Map.of("task_id", "same-task", "account_id", 10,
                "result", Map.of("status", "success")), session);
        assertEquals("success", original.get().get("status"));
    }

    @Test
    void dispatchOrderCheckRejectsSecondTaskForSameAccount() {
        registry.bindAgent(1, openSession());
        registry.bindAgent(2, openSession());

        registry.dispatchOrderCheck(1, "order-1", "https://example.test", "user", "password",
                "form", Map.of(), 1, 10);

        assertThrows(IllegalStateException.class, () -> registry.dispatchOrderCheck(2, "order-2",
                "https://example.test", "user", "password", "form", Map.of(), 1, 10));
        assertEquals("order-1", registry.getAccountTask(10).taskId);
    }

    @Test
    void disconnectingReplacedSessionDoesNotEvictCurrentConnection() {
        WebSocketSession oldSession = openSession();
        WebSocketSession newSession = openSession();
        registry.bindAgent(1, oldSession);
        registry.bindAgent(1, newSession);

        registry.onAgentDisconnect(1, oldSession);

        assertEquals(1, registry.pickAgent(1));
        verify(machineService, never()).getById(1);
    }

    @Test
    void replacingAgentSessionFailsOldTasksAndReleasesAccountReservation() throws Exception {
        WebSocketSession oldSession = openSession();
        WebSocketSession newSession = openSession();
        registry.bindAgent(1, oldSession);
        var oldTask = registry.dispatchLogin(1, "old-task", false, "https://example.test",
                "user", "password", "form", Map.of(), 1, 10);

        registry.bindAgent(1, newSession);

        assertEquals("failed", oldTask.get(1, java.util.concurrent.TimeUnit.SECONDS).get("status"));
        verify(oldSession).close();
        assertDoesNotThrow(() -> registry.dispatchLogin(1, "new-task", false,
                "https://example.test", "user", "password", "form", Map.of(), 1, 10));
    }

    @Test
    void cleanupLoginTaskQuarantinesTaskIdFromLateResults() {
        registry.bindAgent(1, openSession());
        registry.dispatchLogin(1, "timeout-task", false, "https://example.test", "user",
                "password", "form", Map.of(), 1, 10);

        registry.cleanupLoginTask("timeout-task");

        assertThrows(IllegalStateException.class, () -> registry.dispatchLogin(1, "timeout-task", false,
                "https://example.test", "user", "password", "form", Map.of(), 1, 10));
    }

    @Test
    void reconnectCleanupCannotRemoveTaskDispatchedToNewSession() throws Exception {
        WebSocketSession oldSession = openSession();
        WebSocketSession newSession = openSession();
        CountDownLatch closeEntered = new CountDownLatch(1);
        CountDownLatch allowClose = new CountDownLatch(1);
        doAnswer(invocation -> {
            closeEntered.countDown();
            allowClose.await(1, TimeUnit.SECONDS);
            return null;
        }).when(oldSession).close();
        registry.bindAgent(1, oldSession);

        Thread reconnect = new Thread(() -> registry.bindAgent(1, newSession));
        reconnect.start();
        closeEntered.await(1, TimeUnit.SECONDS);
        var newTask = registry.dispatchLogin(1, "new-session-task", false,
                "https://example.test", "user", "password", "form", Map.of(), 1, 10);
        allowClose.countDown();
        reconnect.join(1000);

        org.junit.jupiter.api.Assertions.assertFalse(newTask.isDone());
    }

    @Test
    void secondCaptchaConnectionDoesNotReplaceEventConnection() throws Exception {
        WebSocketSession eventSession = openSession();
        WebSocketSession inputSession = openSession();
        registry.registerCaptcha("captcha-task", eventSession);
        registry.registerCaptcha("captcha-task", inputSession);

        registry.forwardEventToFrontend(Map.of("task_id", "captcha-task", "event", "ready"));
        registry.removeCaptcha("captcha-task", inputSession);
        registry.forwardEventToFrontend(Map.of("task_id", "captcha-task", "event", "success"));

        verify(eventSession, times(2)).sendMessage(org.mockito.ArgumentMatchers.any());
        verify(inputSession, never()).sendMessage(org.mockito.ArgumentMatchers.any());
    }

    private WebSocketSession openSession() {
        WebSocketSession session = mock(WebSocketSession.class);
        when(session.isOpen()).thenReturn(true);
        return session;
    }
}
