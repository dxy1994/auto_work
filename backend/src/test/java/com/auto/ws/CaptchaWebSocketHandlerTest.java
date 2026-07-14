package com.auto.ws;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.web.socket.TextMessage;
import org.springframework.web.socket.WebSocketSession;

import java.util.HashMap;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class CaptchaWebSocketHandlerTest {

    @Test
    void captchaAckReportsFailureWhenAgentCannotReceiveInput() throws Exception {
        AgentRegistry registry = mock(AgentRegistry.class);
        WebSocketSession session = mock(WebSocketSession.class);
        HashMap<String, Object> attributes = new HashMap<>();
        attributes.put("taskId", "task-1");
        when(session.getAttributes()).thenReturn(attributes);
        when(registry.sendCaptchaInput("task-1", "1234")).thenReturn(false);
        CaptchaWebSocketHandler handler = new CaptchaWebSocketHandler(registry, new ObjectMapper());

        handler.handleTextMessage(session,
                new TextMessage("{\"type\":\"captcha_input\",\"value\":\"1234\"}"));

        ArgumentCaptor<TextMessage> message = ArgumentCaptor.forClass(TextMessage.class);
        verify(session).sendMessage(message.capture());
        var ack = new ObjectMapper().readTree(message.getValue().getPayload());
        assertEquals("failed", ack.get("status").asText());
    }
}
