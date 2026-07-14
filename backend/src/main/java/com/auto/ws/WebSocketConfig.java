package com.auto.ws;

import org.springframework.context.annotation.Configuration;
import org.springframework.web.socket.config.annotation.EnableWebSocket;
import org.springframework.web.socket.config.annotation.WebSocketConfigurer;
import org.springframework.web.socket.config.annotation.WebSocketHandlerRegistry;

/**
 * WebSocket 端点注册：
 * <ul>
 *   <li>/api/agent/ws — worker 接入通道</li>
 *   <li>/api/automation/ws/captcha/{task_id} — 前端验证码通道</li>
 * </ul>
 */
@Configuration
@EnableWebSocket
public class WebSocketConfig implements WebSocketConfigurer {

    private final AgentWebSocketHandler agentHandler;
    private final CaptchaWebSocketHandler captchaHandler;

    public WebSocketConfig(AgentWebSocketHandler agentHandler, CaptchaWebSocketHandler captchaHandler) {
        this.agentHandler = agentHandler;
        this.captchaHandler = captchaHandler;
    }

    @Override
    public void registerWebSocketHandlers(WebSocketHandlerRegistry registry) {
        registry.addHandler(agentHandler, "/api/agent/ws")
                .setAllowedOriginPatterns("*");
        registry.addHandler(captchaHandler, "/api/automation/ws/captcha/*")
                .setAllowedOriginPatterns("*");
    }
}
