package com.auto.trade;

import com.auto.entity.GameItemOrder;
import com.auto.entity.GameScript;
import com.auto.entity.RegionScript;
import com.auto.entity.TradeAssignment;
import com.auto.entity.TradeEvent;
import com.auto.service.GameItemOrderService;
import com.auto.service.GameScriptService;
import com.auto.service.RegionScriptService;
import com.auto.service.TradeAssignmentService;
import com.auto.service.TradeEventService;
import com.auto.ws.AgentRegistry;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/** 游戏最终确认前，向订单聊天发送确认内容并等待买家明确回复。 */
@Service
public class TradeFinalConfirmationService {

    public static final String CATEGORY = "确认";
    public static final String PURPOSE = "trade_final_confirmation";
    private static final Logger log =
            LoggerFactory.getLogger(TradeFinalConfirmationService.class);

    private final GameItemOrderService orderService;
    private final TradeAssignmentService assignmentService;
    private final GameScriptService gameScriptService;
    private final RegionScriptService regionScriptService;
    private final ChatDispatchService chatDispatchService;
    private final TradeEventService tradeEventService;
    private final AgentRegistry agentRegistry;
    private final Map<String, PendingConfirmation> pending =
            new ConcurrentHashMap<>();

    public TradeFinalConfirmationService(
            GameItemOrderService orderService,
            TradeAssignmentService assignmentService,
            GameScriptService gameScriptService,
            RegionScriptService regionScriptService,
            ChatDispatchService chatDispatchService,
            TradeEventService tradeEventService,
            AgentRegistry agentRegistry) {
        this.orderService = orderService;
        this.assignmentService = assignmentService;
        this.gameScriptService = gameScriptService;
        this.regionScriptService = regionScriptService;
        this.chatDispatchService = chatDispatchService;
        this.tradeEventService = tradeEventService;
        this.agentRegistry = agentRegistry;
    }

    public void begin(
            String assignmentId,
            int gameMachineId,
            String requestId,
            String screenshotPath) {
        if (requestId == null || requestId.isBlank() || requestId.length() > 100) {
            throw new IllegalStateException("最终确认请求编号无效");
        }
        TradeAssignment assignment = assignmentService.getOne(
                new LambdaQueryWrapper<TradeAssignment>()
                        .eq(TradeAssignment::getAssignmentId, assignmentId),
                false);
        if (assignment == null
                || !Integer.valueOf(gameMachineId).equals(assignment.getMachineId())) {
            throw new IllegalStateException("交易指派不存在或与游戏机器不匹配");
        }
        GameItemOrder order = orderService.getById(assignment.getOrderId());
        if (order == null || !assignmentId.equals(order.getAssignmentId())) {
            throw new IllegalStateException("订单不存在或交易指派已失效");
        }
        if ("completed".equals(order.getStatus())
                || "completed".equals(order.getDeliveryStatus())
                || "wait_web_confirm".equals(order.getDeliveryStatus())) {
            throw new IllegalStateException("游戏交易已经完成，无需再次发送最终确认图片");
        }
        String storedPath = String.valueOf(screenshotPath == null ? "" : screenshotPath).trim();
        if (!storedPath.startsWith("/uploads/trade-screenshots/")
                || storedPath.length() > 512
                || storedPath.contains("..")) {
            throw new IllegalStateException("最终确认缺少有效的交易截图");
        }

        List<Map<String, Object>> messages = confirmationScripts(order);
        if (messages.isEmpty()) {
            throw new IllegalStateException(
                    "未配置启用的“确认”分类话术，请在游戏或对应大区话术中新增");
        }
        messages.add(Map.of("type", "image", "image_url", storedPath));

        PendingConfirmation value = new PendingConfirmation(
                assignmentId, order.getId(), gameMachineId, 0, storedPath);
        if (pending.putIfAbsent(requestId, value) != null) {
            throw new IllegalStateException("最终确认请求编号重复");
        }
        try {
            ChatDispatchService.DispatchReceipt receipt =
                    chatDispatchService.dispatchTradeFinalConfirmation(
                            order.getId(), requestId, messages);
            pending.computeIfPresent(
                    requestId,
                    (key, current) -> current.withMonitorMachineId(
                            receipt.machineId()));
            appendEvent(
                    order,
                    "trade_final_confirmation_waiting",
                    "确认话术与交易截图已发送，正在等待买家韩文肯定回复",
                    Map.of(
                            "request_id", requestId,
                            "game_machine_id", gameMachineId,
                            "monitor_machine_id", receipt.machineId(),
                            "screenshot_path", storedPath));
        } catch (RuntimeException e) {
            pending.remove(requestId);
            throw e;
        }
    }

    public void handleChatResult(
            int monitorMachineId,
            String requestId,
            int orderId,
            boolean success,
            String message,
            Map<String, Object> details) {
        PendingConfirmation value = pending.remove(requestId);
        if (value == null) {
            log.info("[TradeFinalConfirmation] 忽略失效回执 request_id={}", requestId);
            return;
        }
        if (value.orderId() != orderId
                || (value.monitorMachineId() > 0
                && value.monitorMachineId() != monitorMachineId)) {
            log.warn(
                    "[TradeFinalConfirmation] 回执来源不匹配 request_id={} order_id={} machine_id={}",
                    requestId, orderId, monitorMachineId);
            sendResult(
                    value, requestId, false, false, "",
                    "FINAL_CONFIRMATION_RESULT_SOURCE_MISMATCH",
                    "聊天确认回执来源不匹配");
            return;
        }

        Map<String, Object> safeDetails = details == null ? Map.of() : details;
        boolean replyReceived = Boolean.TRUE.equals(
                safeDetails.get("reply_received"));
        boolean affirmative = Boolean.TRUE.equals(
                safeDetails.get("affirmative_reply"));
        String replyText = safe(safeDetails.get("reply_text"));
        boolean approved = success && replyReceived && affirmative;
        String error = approved
                ? ""
                : normalizeMessage(
                        message,
                        replyReceived
                                ? "买家回复不是韩文肯定答复"
                                : "等待买家韩文肯定回复超时");
        String errorCode = approved
                ? ""
                : finalConfirmationErrorCode(
                        safe(safeDetails.get("error_code")),
                        error,
                        replyReceived);

        chatDispatchService.handleResult(
                monitorMachineId, requestId, orderId, approved,
                approved ? "已收到买家韩文肯定回复" : error);
        GameItemOrder order = orderService.getById(orderId);
        if (order != null) {
            Map<String, Object> payload = new LinkedHashMap<>();
            payload.put("request_id", requestId);
            payload.put("monitor_machine_id", monitorMachineId);
            payload.put("reply_received", replyReceived);
            payload.put("affirmative_reply", affirmative);
            payload.put("reply_text", replyText);
            appendEvent(
                    order,
                    approved
                            ? "trade_final_confirmation_approved"
                            : "trade_final_confirmation_rejected",
                    approved
                            ? "买家已肯定回复，允许点击游戏最终确认"
                            : error,
                    payload);
        }
        sendResult(
                value, requestId, approved, replyReceived, replyText,
                errorCode, error);
    }

    private void sendResult(
            PendingConfirmation value,
            String requestId,
            boolean approved,
            boolean replyReceived,
            String replyText,
            String errorCode,
            String error) {
        if (!agentRegistry.sendTradeFinalConfirmationResult(
                value.gameMachineId(), requestId, approved, replyReceived,
                replyText, errorCode, error)) {
            log.warn(
                    "[TradeFinalConfirmation] 游戏机器回执发送失败 request_id={} machine_id={}",
                    requestId, value.gameMachineId());
        }
    }

    private static String finalConfirmationErrorCode(
            String monitorErrorCode,
            String error,
            boolean replyReceived) {
        if (replyReceived) {
            return "BUYER_FINAL_REPLY_REJECTED";
        }
        return switch (monitorErrorCode) {
            case "CHAT_IMAGE_SEND_FAILED" ->
                    "FINAL_CONFIRMATION_IMAGE_SEND_FAILED";
            case "CHAT_TEXT_SEND_FAILED" ->
                    "FINAL_CONFIRMATION_TEXT_SEND_FAILED";
            case "CHAT_REPLY_ANCHOR_NOT_FOUND" ->
                    "FINAL_CONFIRMATION_ANCHOR_NOT_FOUND";
            case "BUYER_FINAL_REPLY_TIMEOUT" -> monitorErrorCode;
            default -> inferLegacyFinalConfirmationErrorCode(error);
        };
    }

    private static String inferLegacyFinalConfirmationErrorCode(String error) {
        String value = error == null ? "" : error;
        if (value.contains("图片") && value.contains("发送失败")) {
            return "FINAL_CONFIRMATION_IMAGE_SEND_FAILED";
        }
        if (value.contains("未在会话中定位") && value.contains("确认")) {
            return "FINAL_CONFIRMATION_ANCHOR_NOT_FOUND";
        }
        if (value.contains("等待买家") && value.contains("超时")) {
            return "BUYER_FINAL_REPLY_TIMEOUT";
        }
        return "FINAL_CONFIRMATION_DISPATCH_FAILED";
    }

    private List<Map<String, Object>> confirmationScripts(GameItemOrder order) {
        List<Map<String, Object>> messages = new ArrayList<>();
        if (order.getGameId() != null) {
            for (GameScript script : gameScriptService.findAllByGameIdAndCategory(
                    order.getGameId(), CATEGORY)) {
                addScript(messages, script.getContent(), script.getImageUrl());
            }
        }
        if (order.getRegionId() != null) {
            for (RegionScript script : regionScriptService.findAllByRegionIdAndCategory(
                    order.getRegionId(), CATEGORY)) {
                addScript(messages, script.getContent(), script.getImageUrl());
            }
        }
        return messages;
    }

    private void addScript(
            List<Map<String, Object>> messages,
            String content,
            String imageUrl) {
        Map<String, Object> message = new LinkedHashMap<>();
        if (content != null && !content.isBlank()) {
            message.put("content", content.trim());
        }
        if (imageUrl != null && !imageUrl.isBlank()) {
            message.put("image_url", imageUrl.trim());
        }
        if (!message.isEmpty()) {
            messages.add(message);
        }
    }

    private void appendEvent(
            GameItemOrder order,
            String type,
            String message,
            Map<String, Object> payload) {
        try {
            TradeEvent event = new TradeEvent();
            event.setOrderId(order.getId());
            event.setAssignmentId(order.getAssignmentId());
            event.setEventType(type);
            event.setFromStatus(order.getDeliveryStatus());
            event.setToStatus(order.getDeliveryStatus());
            event.setMessage(message);
            event.setPayload(payload);
            tradeEventService.save(event);
        } catch (RuntimeException e) {
            log.warn(
                    "[TradeFinalConfirmation] 事件记录失败 order_id={} type={}: {}",
                    order.getId(), type, e.getMessage());
        }
    }

    private static String safe(Object value) {
        return value == null ? "" : value.toString().strip();
    }

    private static String normalizeMessage(String value, String fallback) {
        String result = value == null ? "" : value.strip();
        if (result.isBlank()) {
            result = fallback;
        }
        return result.substring(0, Math.min(300, result.length()));
    }

    private record PendingConfirmation(
            String assignmentId,
            int orderId,
            int gameMachineId,
            int monitorMachineId,
            String screenshotPath) {
        private PendingConfirmation withMonitorMachineId(int machineId) {
            return new PendingConfirmation(
                    assignmentId, orderId, gameMachineId, machineId,
                    screenshotPath);
        }
    }
}
