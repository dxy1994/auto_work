package com.auto.ws;

import tools.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.socket.CloseStatus;
import org.springframework.web.socket.TextMessage;
import org.springframework.web.socket.WebSocketSession;
import org.springframework.web.socket.handler.TextWebSocketHandler;

import java.net.URI;
import java.util.Map;

/**
 * 前端验证码 WebSocket 处理器（/api/automation/ws/captcha/{task_id}）。
 *
 * <p>对应原 Python routers/automation.py 的 captcha_ws：接收前端 captcha_input，
 * 转发给执行该任务的 agent，并回 captcha_received。
 */
@Component
public class CaptchaWebSocketHandler extends TextWebSocketHandler {

    private static final Logger log = LoggerFactory.getLogger(CaptchaWebSocketHandler.class);
    private static final String ATTR_TASK_ID = "taskId";

    private final AgentRegistry registry;
    private final ObjectMapper objectMapper;

    public CaptchaWebSocketHandler(AgentRegistry registry, ObjectMapper objectMapper) {
        this.registry = registry;
        this.objectMapper = objectMapper;
    }

    @Override
    public void afterConnectionEstablished(WebSocketSession session) {
        String taskId = extractTaskId(session);
        session.getAttributes().put(ATTR_TASK_ID, taskId);
        registry.registerCaptcha(taskId, session);
    }

    @Override
    @SuppressWarnings("unchecked")
    protected void handleTextMessage(WebSocketSession session, TextMessage message) throws Exception {
        String taskId = (String) session.getAttributes().get(ATTR_TASK_ID);
        Map<String, Object> msg;
        try {
            msg = objectMapper.readValue(message.getPayload(), Map.class);
        } catch (Exception e) {
            return;
        }
        if ("captcha_input".equals(String.valueOf(msg.get("type")))) {
            String value = msg.get("value") == null ? "" : msg.get("value").toString();
            boolean forwarded = registry.sendCaptchaInput(taskId, value);
            Map<String, Object> ack = forwarded
                    ? Map.of("type", "captcha_received", "status", "ok")
                    : Map.of("type", "captcha_received", "status", "failed",
                            "message", "任务不存在或 agent 已离线");
            session.sendMessage(new TextMessage(objectMapper.writeValueAsString(ack)));
        }
    }

    @Override
    public void afterConnectionClosed(WebSocketSession session, CloseStatus status) {
        String taskId = (String) session.getAttributes().get(ATTR_TASK_ID);
        if (taskId != null) {
            registry.removeCaptcha(taskId, session);
        }
    }

    @Override
    public void handleTransportError(WebSocketSession session, Throwable exception) {
        String taskId = (String) session.getAttributes().get(ATTR_TASK_ID);
        if (taskId != null) {
            registry.removeCaptcha(taskId, session);
        }
        log.warn("[Captcha] WS 传输异常: {}", exception.getMessage());
    }

    /** 从 URI 路径尾段取 task_id（/api/automation/ws/captcha/{task_id}）。 */
    private String extractTaskId(WebSocketSession session) {
        URI uri = session.getUri();
        if (uri == null) {
            return "";
        }
        String path = uri.getPath();
        int idx = path.lastIndexOf('/');
        return idx >= 0 ? path.substring(idx + 1) : path;
    }
}
