package com.auto.ws;

import com.auto.service.WirelessHidDeviceManager;
import com.auto.service.WirelessHidDeviceManager.WorkerBinding;
import com.auto.trade.ChatDispatchService;
import com.auto.trade.DeliveryConfirmationService;
import com.auto.trade.TradeDispatchCoordinator;
import com.auto.trade.MarketplaceOrderIngestionService;
import com.auto.trade.GreetingDispatchService;
import com.auto.trade.OrderDetectedMessage;
import tools.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.socket.CloseStatus;
import org.springframework.web.socket.TextMessage;
import org.springframework.web.socket.WebSocketSession;
import org.springframework.web.socket.handler.TextWebSocketHandler;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * Agent 接入 WebSocket 处理器（/api/agent/ws）。
 *
 * <p>对应原 Python routers/agent.py 的 agent_ws：处理 worker 的
 * register / heartbeat / task_status / task_result 上行消息。
 */
@Component
public class AgentWebSocketHandler extends TextWebSocketHandler {

    private static final Logger log = LoggerFactory.getLogger(AgentWebSocketHandler.class);
    private static final String ATTR_MACHINE_ID = "machineId";
    private static final int MAX_MESSAGE_CHARS = 4 * 1024 * 1024;

    private final AgentRegistry registry;
    private final ObjectMapper objectMapper;
    private final TradeDispatchCoordinator tradeCoordinator;
    private final MarketplaceOrderIngestionService orderIngestionService;
    private final GreetingDispatchService greetingDispatchService;
    private final ChatDispatchService chatDispatchService;
    private final DeliveryConfirmationService deliveryConfirmationService;
    private final WirelessHidDeviceManager wirelessHidDeviceManager;

    public AgentWebSocketHandler(
            AgentRegistry registry,
            ObjectMapper objectMapper,
            TradeDispatchCoordinator tradeCoordinator,
            MarketplaceOrderIngestionService orderIngestionService,
            GreetingDispatchService greetingDispatchService,
            ChatDispatchService chatDispatchService,
            DeliveryConfirmationService deliveryConfirmationService,
            WirelessHidDeviceManager wirelessHidDeviceManager) {
        this.registry = registry;
        this.objectMapper = objectMapper;
        this.tradeCoordinator = tradeCoordinator;
        this.orderIngestionService = orderIngestionService;
        this.greetingDispatchService = greetingDispatchService;
        this.chatDispatchService = chatDispatchService;
        this.deliveryConfirmationService = deliveryConfirmationService;
        this.wirelessHidDeviceManager = wirelessHidDeviceManager;
    }

    @Override
    @SuppressWarnings("unchecked")
    protected void handleTextMessage(WebSocketSession session, TextMessage message) throws Exception {
        if (message.getPayloadLength() > MAX_MESSAGE_CHARS) {
            log.warn("[Agent] 忽略超过 4MiB 的上行消息");
            return;
        }
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
        try {
            switch (type) {
                case "register" -> {
                    Integer machineId = registry.handleRegister(raw);
                    session.getAttributes().put(ATTR_MACHINE_ID, machineId);
                    registry.bindAgent(machineId, session);
                    Map<String, Object> ack = new LinkedHashMap<>();
                    ack.put("type", "registered");
                    ack.put("machine_id", machineId);
                    if ("game_executor".equals(str(raw.get("role")))) {
                        appendHardwareBinding(ack, machineId, null);
                    }
                    session.sendMessage(new TextMessage(objectMapper.writeValueAsString(ack)));
                    log.info("[Agent] 机器已注册并上线 machine_id={} mac={}", machineId, raw.get("mac"));
                }
                case "hardware_binding_request" -> handleHardwareBindingRequest(session, raw);
                case "heartbeat" -> {
                    Integer machineId = machineId(session);
                    if (machineId != null) {
                        registry.updateHeartbeat(machineId, raw);
                    }
                }
                case "task_status" -> registry.handleTaskStatus(raw, session);
                case "task_result" -> registry.handleTaskResult(raw, session);
                case "trade_offer_decision" -> handleTradeDecision(session, raw);
                case "trade_status" -> handleTradeStatus(session, raw);
                case "trade_buyer_review" -> handleTradeBuyerReview(session, raw);
                case "trade_game_screenshot" -> handleTradeGameScreenshot(session, raw);
                case "order_detected" -> handleOrderDetected(session, raw);
                case "check_orders" -> handleCheckOrders(session, raw);
                case "greeting_result" -> handleGreetingResult(raw);
                case "chat_result" -> handleChatResult(session, raw);
                default -> log.info("[Agent] 未知上行消息类型: {}", type);
            }
        } catch (Exception e) {
            log.error("[Agent] 处理上行消息异常 type={}: {}", type, e.getMessage(), e);
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
                    str(raw.get("message")),
                    str(raw.get("error_code")));
        } catch (IllegalStateException e) {
            log.warn("[Trade] 忽略无效交易状态 machine_id={}: {}", machineId, e.getMessage());
        }
    }

    private void handleHardwareBindingRequest(
            WebSocketSession session,
            Map<String, Object> raw) throws Exception {
        Integer machineId = machineId(session);
        String macAddress = machineId == null ? str(raw.get("mac")) : null;
        Map<String, Object> response = new LinkedHashMap<>();
        response.put("type", "hardware_binding");
        response.put("machine_id", machineId);
        appendHardwareBinding(response, machineId, macAddress);
        synchronized (session) {
            session.sendMessage(new TextMessage(objectMapper.writeValueAsString(response)));
        }
    }

    private void appendHardwareBinding(
            Map<String, Object> target,
            Integer machineId,
            String macAddress) {
        try {
            WorkerBinding binding;
            if (machineId != null) {
                binding = wirelessHidDeviceManager.prepareWorkerBinding(machineId);
            } else if (macAddress != null && !macAddress.isBlank()) {
                binding = wirelessHidDeviceManager.prepareWorkerBindingByMac(macAddress);
            } else {
                throw new IllegalArgumentException("缺少 machine_id 或 mac");
            }
            target.put("wireless_hid", binding == null ? null : bindingPayload(binding));
            target.put(
                    "hardware_error",
                    binding == null ? "当前机器尚未绑定键鼠设备" : null);
        } catch (Exception e) {
            target.put("wireless_hid", null);
            target.put("hardware_error", e.getMessage());
        }
    }

    private Map<String, Object> bindingPayload(WorkerBinding binding) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("record_id", binding.recordId());
        payload.put("device_id", binding.deviceId());
        payload.put("name", binding.name());
        payload.put("ip", binding.ip());
        payload.put("control_port", binding.controlPort());
        return payload;
    }

    private void handleTradeBuyerReview(WebSocketSession session, Map<String, Object> raw) {
        Integer machineId = machineId(session);
        if (machineId == null || !registry.isCurrentSession(machineId, session)) {
            log.warn("[Trade] 忽略非当前机器会话的买家审核请求 machine_id={}", machineId);
            return;
        }
        Object confidence = raw.get("ocr_confidence");
        tradeCoordinator.handleBuyerReview(
                str(raw.get("assignment_id")),
                machineId,
                str(raw.get("review_id")),
                str(raw.get("observed_buyer")),
                confidence instanceof Number number ? number.doubleValue() : -1.0,
                str(raw.get("screenshot_data_url")));
    }

    private void handleTradeGameScreenshot(WebSocketSession session, Map<String, Object> raw) {
        Integer machineId = machineId(session);
        String requestId = str(raw.get("request_id"));
        boolean success = false;
        String error = null;
        try {
            if (machineId == null || !registry.isCurrentSession(machineId, session)) {
                throw new IllegalStateException("不是当前机器会话");
            }
            tradeCoordinator.handleGameTradeScreenshot(
                    str(raw.get("assignment_id")),
                    machineId,
                    str(raw.get("screenshot_path")));
            success = true;
        } catch (Exception e) {
            error = e.getMessage();
            log.warn("[Trade] 游戏交易截图保存失败 machine_id={}: {}", machineId, error);
        }
        try {
            Map<String, Object> response = new java.util.LinkedHashMap<>();
            response.put("type", "trade_game_screenshot_saved");
            response.put("request_id", requestId);
            response.put("success", success);
            response.put("error", error);
            synchronized (session) {
                session.sendMessage(new TextMessage(objectMapper.writeValueAsString(response)));
            }
        } catch (Exception e) {
            log.warn("[Trade] 游戏交易截图保存回执发送失败: {}", e.getMessage());
        }
    }

    private static String str(Object value) {
        return value == null ? null : value.toString();
    }

    @SuppressWarnings("unchecked")
    private void handleCheckOrders(WebSocketSession session, Map<String, Object> raw) {
        Integer machineId = machineId(session);
        if (machineId == null || !registry.isCurrentSession(machineId, session)) {
            return;
        }
        Integer websiteId = asInt(raw.get("website_id"));
        Object nosObj = raw.get("source_order_nos");
        String requestId = str(raw.get("request_id"));
        if (websiteId == null || !(nosObj instanceof List<?>) || requestId == null) {
            log.warn("[Order] check_orders 参数不完整 machine_id={}", machineId);
            return;
        }
        List<String> sourceOrderNos = ((List<?>) nosObj).stream()
                .map(Object::toString)
                .toList();
        Set<String> existing = orderIngestionService.findExistingSourceOrderNos(
                websiteId, sourceOrderNos);
        try {
            Map<String, Object> resp = Map.of(
                    "type", "orders_check_result",
                    "request_id", requestId,
                    "existing_ids", existing);
            session.sendMessage(new TextMessage(
                    objectMapper.writeValueAsString(resp)));
        } catch (Exception e) {
            log.warn("[Order] 查重响应发送失败: {}", e.getMessage());
        }
    }

    @SuppressWarnings("unchecked")
    private void handleOrderDetected(WebSocketSession session, Map<String, Object> raw) {
        Integer machineId = machineId(session);
        if (machineId == null || !registry.isCurrentSession(machineId, session)) {
            log.warn("[Order] 忽略非当前机器会话的订单观察 machine_id={}", machineId);
            return;
        }
        Integer accountId = asInt(raw.get("account_id"));
        Object order = raw.get("order");
        if (accountId == null || !(order instanceof Map<?, ?>)) {
            log.warn("[Order] 忽略字段不完整的订单观察 machine_id={}", machineId);
            return;
        }
        try {
            OrderDetectedMessage message = objectMapper.convertValue(
                    (Map<String, Object>) order, OrderDetectedMessage.class);
            orderIngestionService.ingest(machineId, accountId, message);
        } catch (Exception e) {
            log.warn("[Order] 订单观察处理失败 machine_id={}: {}", machineId, e.getMessage());
        }
    }

    private void handleGreetingResult(Map<String, Object> raw) {
        Integer orderId = asInt(raw.get("order_id"));
        Boolean success = raw.get("success") instanceof Boolean b ? b : false;
        String message = str(raw.get("message"));
        if (orderId == null) {
            log.warn("[Greeting] greeting_result 缺少 order_id");
            return;
        }
        try {
            greetingDispatchService.handleResult(orderId, success, message);
        } catch (Exception e) {
            log.error("[Greeting] 处理招呼回馈异常 order_id={}: {}", orderId, e.getMessage(), e);
        }
    }

    private void handleChatResult(WebSocketSession session, Map<String, Object> raw) {
        Integer machineId = machineId(session);
        if (machineId == null || !registry.isCurrentSession(machineId, session)) {
            log.warn("[Chat] 忽略非当前机器会话的聊天回执 machine_id={}", machineId);
            return;
        }
        Integer orderId = asInt(raw.get("order_id"));
        String requestId = str(raw.get("request_id"));
        if (orderId == null || requestId == null || requestId.isBlank()) {
            log.warn("[Chat] chat_result 缺少 order_id 或 request_id");
            return;
        }
        String purpose = str(raw.get("purpose"));
        if (DeliveryConfirmationService.PURPOSE.equals(purpose)) {
            deliveryConfirmationService.handleResult(
                    machineId,
                    requestId,
                    orderId,
                    Boolean.TRUE.equals(raw.get("success")),
                    str(raw.get("message")),
                    stringObjectMap(raw.get("details")));
        } else {
            chatDispatchService.handleResult(
                    machineId,
                    requestId,
                    orderId,
                    Boolean.TRUE.equals(raw.get("success")),
                    str(raw.get("message")));
        }
    }

    private static Integer asInt(Object value) {
        if (value instanceof Number number) {
            return number.intValue();
        }
        try {
            return value == null ? null : Integer.parseInt(value.toString());
        } catch (NumberFormatException e) {
            return null;
        }
    }

    private static Map<String, Object> stringObjectMap(Object value) {
        if (!(value instanceof Map<?, ?> source)) {
            return Map.of();
        }
        Map<String, Object> result = new LinkedHashMap<>();
        source.forEach((key, item) -> {
            if (key != null) {
                result.put(key.toString(), item);
            }
        });
        return result;
    }
}
