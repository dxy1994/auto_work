package com.auto.ws;

import com.auto.trade.TradeDispatchCoordinator;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.socket.CloseStatus;
import org.springframework.web.socket.TextMessage;
import org.springframework.web.socket.WebSocketSession;
import org.springframework.web.socket.handler.TextWebSocketHandler;

import java.util.Map;

/**
 * Agent 接入 WebSocket 处理器（/api/agent/ws）。
 *
 * <p>对应原 Python routers/agent.py 的 agent_ws：处理 worker 的
 * register / heartbeat / task_status / task_result / task_event /
 * captcha_required 上行消息。
 */
@Component
public class AgentWebSocketHandler extends TextWebSocketHandler {

    private static final Logger log = LoggerFactory.getLogger(AgentWebSocketHandler.class);
    private static final String ATTR_MACHINE_ID = "machineId";

    private final AgentRegistry registry;
    private final ObjectMapper objectMapper;
    private final TradeDispatchCoordinator tradeCoordinator;

    public AgentWebSocketHandler(
            AgentRegistry registry,
            ObjectMapper objectMapper,
            TradeDispatchCoordinator tradeCoordinator) {
        this.registry = registry;
        this.objectMapper = objectMapper;
        this.tradeCoordinator = tradeCoordinator;
    }

    @Override
    @SuppressWarnings("unchecked")
    protected void handleTextMessage(WebSocketSession session, TextMessage message) throws Exception {
        Map<String, Object> raw;
        try {
            raw = objectMapper.readValue(message.getPayload(), Map.class);
        } catch (Exception e) {
            log.warn("[Agent] 无法解析上行消息: {}", e.getMessage());
            return;
        }
        String type = raw.get("type") == null ? null : raw.get("type").toString();
        if (type == null) {
            return;
        }
        switch (type) {
            case "register" -> {
                Integer machineId = registry.handleRegister(raw);
                session.getAttributes().put(ATTR_MACHINE_ID, machineId);
                registry.bindAgent(machineId, session);
                Map<String, Object> ack = Map.of("type", "registered", "machine_id", machineId);
                session.sendMessage(new TextMessage(objectMapper.writeValueAsString(ack)));
                log.info("[Agent] 机器已注册并上线 machine_id={} mac={}", machineId, raw.get("mac"));
            }
            case "heartbeat" -> {
                Integer machineId = machineId(session);
                if (machineId != null) {
                    registry.updateHeartbeat(machineId, raw);
                }
            }
            case "task_status" -> registry.handleTaskStatus(raw, session);
            case "task_result" -> registry.handleTaskResult(raw, session);
            case "task_event" -> registry.forwardEventToFrontend(raw);
            case "captcha_required" -> registry.forwardCaptchaRequired(raw);
            case "trade_offer_decision" -> handleTradeDecision(session, raw);
            case "trade_status" -> handleTradeStatus(session, raw);
            default -> log.info("[Agent] 未知上行消息类型: {}", type);
        }
    }

    @Override
    public void afterConnectionClosed(WebSocketSession session, CloseStatus status) {
        Integer machineId = machineId(session);
        if (machineId != null) {
            registry.onAgentDisconnect(machineId, session);
            log.info("[Agent] 机器断线并下线 machine_id={}", machineId);
        }
    }

    @Override
    public void handleTransportError(WebSocketSession session, Throwable exception) {
        log.warn("[Agent] WS 传输异常: {}", exception.getMessage());
    }

    private Integer machineId(WebSocketSession session) {
        Object v = session.getAttributes().get(ATTR_MACHINE_ID);
        return v instanceof Integer ? (Integer) v : null;
    }

    private void handleTradeDecision(WebSocketSession session, Map<String, Object> raw) {
        Integer machineId = machineId(session);
        if (machineId == null || !registry.isCurrentSession(machineId, session)) {
            log.warn("[Trade] 忽略非当前机器会话的 offer 决策 machine_id={}", machineId);
            return;
        }
        try {
            tradeCoordinator.handleDecision(
                    str(raw.get("assignment_id")),
                    machineId,
                    Boolean.TRUE.equals(raw.get("accepted")),
                    str(raw.get("reason")));
        } catch (IllegalStateException e) {
            log.warn("[Trade] 忽略无效 offer 决策 machine_id={}: {}", machineId, e.getMessage());
        }
    }

    private void handleTradeStatus(WebSocketSession session, Map<String, Object> raw) {
        Integer machineId = machineId(session);
        if (machineId == null || !registry.isCurrentSession(machineId, session)) {
            log.warn("[Trade] 忽略非当前机器会话的状态 machine_id={}", machineId);
            return;
        }
        try {
            tradeCoordinator.handleStatus(
                    str(raw.get("assignment_id")),
                    machineId,
                    str(raw.get("status")),
                    str(raw.get("message")));
        } catch (IllegalStateException e) {
            log.warn("[Trade] 忽略无效交易状态 machine_id={}: {}", machineId, e.getMessage());
        }
    }

    private static String str(Object value) {
        return value == null ? null : value.toString();
    }
}
