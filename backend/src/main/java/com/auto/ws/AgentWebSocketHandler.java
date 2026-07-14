package com.auto.ws;

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

    public AgentWebSocketHandler(AgentRegistry registry, ObjectMapper objectMapper) {
        this.registry = registry;
        this.objectMapper = objectMapper;
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
                    registry.updateHeartbeat(machineId);
                }
            }
            case "task_status" -> registry.handleTaskStatus(raw, session);
            case "task_result" -> registry.handleTaskResult(raw, session);
            case "task_event" -> registry.forwardEventToFrontend(raw);
            case "captcha_required" -> registry.forwardCaptchaRequired(raw);
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
}
