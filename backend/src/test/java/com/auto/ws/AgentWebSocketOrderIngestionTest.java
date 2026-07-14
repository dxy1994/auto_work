package com.auto.ws;

import com.auto.trade.MarketplaceOrderIngestionService;
import com.auto.trade.OrderDetectedMessage;
import com.auto.trade.TradeDispatchCoordinator;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.web.socket.TextMessage;
import org.springframework.web.socket.WebSocketSession;

import java.util.HashMap;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class AgentWebSocketOrderIngestionTest {

    private AgentRegistry registry;
    private MarketplaceOrderIngestionService ingestionService;
    private AgentWebSocketHandler handler;
    private WebSocketSession session;

    @BeforeEach
    void setUp() {
        registry = mock(AgentRegistry.class);
        ingestionService = mock(MarketplaceOrderIngestionService.class);
        ObjectMapper mapper = new ObjectMapper();
        mapper.setPropertyNamingStrategy(PropertyNamingStrategies.SNAKE_CASE);
        handler = new AgentWebSocketHandler(
                registry, mapper, mock(TradeDispatchCoordinator.class), ingestionService);
        session = mock(WebSocketSession.class);
        HashMap<String, Object> attributes = new HashMap<>();
        attributes.put("machineId", 7);
        when(session.getAttributes()).thenReturn(attributes);
    }

    @Test
    void currentMachineSessionCanReportDetectedOrder() throws Exception {
        when(registry.isCurrentSession(7, session)).thenReturn(true);

        handler.handleTextMessage(session, new TextMessage("""
                {"type":"order_detected","account_id":12,"order":{
                  "platform":"itembay","source_order_no":"B-300",
                  "region_external_key":"1","asset_type":"adena",
                  "asset_amount":2500000,"buyer_character":"buyer",
                  "platform_status":"paid","raw_title":"adena"}}
                """));

        verify(ingestionService).ingest(eq(7), eq(12), any(OrderDetectedMessage.class));
    }

    @Test
    void replacedSessionCannotIngestOrder() throws Exception {
        when(registry.isCurrentSession(7, session)).thenReturn(false);

        handler.handleTextMessage(session, new TextMessage("""
                {"type":"order_detected","account_id":12,"order":{}}
                """));

        verify(ingestionService, never()).ingest(any(Integer.class), any(Integer.class), any());
    }
}
