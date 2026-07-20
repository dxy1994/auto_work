package com.auto.ws;

import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Bean;
import org.springframework.web.socket.config.annotation.EnableWebSocket;
import org.springframework.web.socket.config.annotation.WebSocketConfigurer;
import org.springframework.web.socket.config.annotation.WebSocketHandlerRegistry;
import org.springframework.web.socket.server.standard.ServletServerContainerFactoryBean;

/**
 * WebSocket 端点注册：
 * <ul>
 *   <li>/api/agent/ws — worker 接入通道</li>
 * </ul>
 */
@Configuration
@EnableWebSocket
public class WebSocketConfig implements WebSocketConfigurer {

    private static final int AGENT_MESSAGE_BUFFER_BYTES = 4 * 1024 * 1024;

    private final AgentWebSocketHandler agentHandler;

    public WebSocketConfig(AgentWebSocketHandler agentHandler) {
        this.agentHandler = agentHandler;
    }

    @Override
    public void registerWebSocketHandlers(WebSocketHandlerRegistry registry) {
        registry.addHandler(agentHandler, "/api/agent/ws")
                .setAllowedOriginPatterns("*");
    }

    @Bean
    public ServletServerContainerFactoryBean webSocketContainer() {
        ServletServerContainerFactoryBean container = new ServletServerContainerFactoryBean();
        container.setMaxTextMessageBufferSize(AGENT_MESSAGE_BUFFER_BYTES);
        container.setMaxBinaryMessageBufferSize(AGENT_MESSAGE_BUFFER_BYTES);
        return container;
    }
}
