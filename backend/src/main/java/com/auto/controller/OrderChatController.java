package com.auto.controller;

import com.auto.trade.ChatDispatchService;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

/** Sends arbitrary ordered text/image messages to an order's platform customer. */
@RestController
@RequestMapping("/api/orders")
public class OrderChatController {

    private final ChatDispatchService chatDispatchService;

    public OrderChatController(ChatDispatchService chatDispatchService) {
        this.chatDispatchService = chatDispatchService;
    }

    @PostMapping("/{orderId}/chat")
    public Map<String, Object> send(
            @PathVariable Integer orderId,
            @RequestBody ChatRequest request) {
        return chatDispatchService
                .dispatchOrderChat(orderId, request == null ? null : request.messages())
                .toPayload();
    }

    public record ChatRequest(List<Map<String, Object>> messages) {
    }
}
