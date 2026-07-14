package com.auto.ws;

import com.auto.trade.TradeDispatchCoordinator;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.web.socket.TextMessage;
import org.springframework.web.socket.WebSocketSession;

import java.util.HashMap;

import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class AgentWebSocketTradeProtocolTest {

    private AgentRegistry registry;
    private TradeDispatchCoordinator coordinator;
    private AgentWebSocketHandler handler;
    private WebSocketSession session;

    @BeforeEach
    void setUp() {
        registry = mock(AgentRegistry.class);
        coordinator = mock(TradeDispatchCoordinator.class);
        handler = new AgentWebSocketHandler(registry, new ObjectMapper(), coordinator);
        session = mock(WebSocketSession.class);
        HashMap<String, Object> attributes = new HashMap<>();
        attributes.put("machineId", 7);
        when(session.getAttributes()).thenReturn(attributes);
    }

    @Test
    void currentMachineSessionCanAcceptTradeOffer() throws Exception {
        when(registry.isCurrentSession(7, session)).thenReturn(true);

        handler.handleTextMessage(session, new TextMessage("""
                {"type":"trade_offer_decision","assignment_id":"a-1","accepted":true}
                """));

        verify(coordinator).handleDecision("a-1", 7, true, null);
    }

    @Test
    void replacedSessionCannotReportTradeStatus() throws Exception {
        when(registry.isCurrentSession(7, session)).thenReturn(false);

        handler.handleTextMessage(session, new TextMessage("""
                {"type":"trade_status","assignment_id":"a-1","status":"started"}
                """));

        verify(coordinator, never()).handleStatus("a-1", 7, "started", null);
    }
}
