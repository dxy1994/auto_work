package com.auto.trade;

import com.auto.entity.GameItemOrder;
import com.auto.entity.TradeEvent;
import com.auto.service.GameItemOrderService;
import com.auto.service.TradeEventService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 游戏交付后的平台收尾：发送 RustFS 截图、关闭聊天页并确认网站商品交付。
 */
@Service
public class DeliveryConfirmationService {

    public static final String PURPOSE = "delivery_confirmation";
    private static final Logger log =
            LoggerFactory.getLogger(DeliveryConfirmationService.class);

    private final ChatDispatchService chatDispatchService;
    private final GameItemOrderService orderService;
    private final ManualOrderStatusService manualOrderStatusService;
    private final TradeEventService tradeEventService;

    public DeliveryConfirmationService(
            ChatDispatchService chatDispatchService,
            GameItemOrderService orderService,
            ManualOrderStatusService manualOrderStatusService,
            TradeEventService tradeEventService) {
        this.chatDispatchService = chatDispatchService;
        this.orderService = orderService;
        this.manualOrderStatusService = manualOrderStatusService;
        this.tradeEventService = tradeEventService;
    }

    public void dispatch(int orderId) {
        GameItemOrder order = orderService.getById(orderId);
        if (order == null || !"wait_web_confirm".equals(order.getDeliveryStatus())) {
            log.info("[DeliveryConfirmation] 订单已离开等待确认状态，跳过 order_id={}", orderId);
            return;
        }
        try {
            appendEvent(
                    order,
                    "trade_screenshot_stored",
                    "最终确认前截图已直传 RustFS",
                    Map.of("screenshot_path", order.getGameTradeScreenshot()));
            ChatDispatchService.DispatchReceipt receipt =
                    chatDispatchService.dispatchDeliveryConfirmation(orderId);
            appendEvent(
                    order,
                    "delivery_confirmation_dispatched",
                    "截图聊天与网站商品交付确认指令已下发",
                    Map.of(
                            "request_id", receipt.requestId(),
                            "machine_id", receipt.machineId(),
                            "screenshot_path", order.getGameTradeScreenshot()));
            log.info(
                    "[DeliveryConfirmation] 指令已下发 order_id={} request_id={} machine_id={}",
                    orderId, receipt.requestId(), receipt.machineId());
        } catch (RuntimeException e) {
            String message = TradeErrorGuidance.ensureGuidance(
                    "WEBSITE_DELIVERY_DISPATCH_FAILED",
                    normalizeMessage(e.getMessage(), "截图聊天与网站交付确认指令下发失败"));
            orderService.updateLastError(
                    orderId, "WEBSITE_DELIVERY_DISPATCH_FAILED", message);
            appendEvent(
                    order,
                    "delivery_confirmation_failed",
                    message,
                    Map.of("stage", "dispatch"));
            log.warn("[DeliveryConfirmation] 指令下发失败 order_id={}: {}", orderId, e.getMessage());
        }
    }

    public void handleResult(
            int machineId,
            String requestId,
            int orderId,
            boolean success,
            String message,
            Map<String, Object> details) {
        Map<String, Object> safeDetails = details == null ? Map.of() : details;
        boolean chatSent = safeDetails.containsKey("chat_sent")
                ? Boolean.TRUE.equals(safeDetails.get("chat_sent"))
                : success;
        boolean chatClosed = safeDetails.containsKey("chat_closed")
                ? Boolean.TRUE.equals(safeDetails.get("chat_closed"))
                : success;
        boolean deliveryConfirmed = safeDetails.containsKey("delivery_confirmed")
                ? Boolean.TRUE.equals(safeDetails.get("delivery_confirmed"))
                : success;
        boolean proofReady = chatSent && chatClosed;
        boolean fullyCompleted =
                success && proofReady && deliveryConfirmed;
        chatDispatchService.handleResult(
                machineId,
                requestId,
                orderId,
                chatSent,
                chatSent ? "交易截图已发送" : message);
        GameItemOrder order = orderService.getById(orderId);
        if (order == null) {
            log.warn("[DeliveryConfirmation] 回执对应订单不存在 order_id={}", orderId);
            return;
        }
        if ("completed".equals(order.getStatus())) {
            log.info("[DeliveryConfirmation] 忽略已完成订单的重复回执 order_id={}", orderId);
            return;
        }
        if (!"wait_web_confirm".equals(order.getDeliveryStatus())) {
            log.info(
                    "[DeliveryConfirmation] 订单状态已变化，忽略迟到回执 order_id={} status={}",
                    orderId, order.getDeliveryStatus());
            return;
        }

        Map<String, Object> proofPayload = Map.of(
                "request_id", requestId,
                "machine_id", machineId,
                "screenshot_path", order.getGameTradeScreenshot(),
                "chat_closed", chatClosed);
        appendEvent(
                order,
                proofReady ? "delivery_proof_sent" : "delivery_proof_failed",
                proofReady
                        ? "交易截图已发送，聊天页已关闭"
                        : chatSent
                                ? "交易截图已发送，但聊天页关闭失败"
                                : "交易截图发送失败",
                proofPayload);

        if (!fullyCompleted) {
            String fallback = !chatSent
                    ? "交易截图发送失败"
                    : !chatClosed
                            ? "交易截图已发送，但聊天页关闭失败"
                            : "网站商品交付确认失败";
            String failureMessage = success ? fallback : message;
            String errorMessage = TradeErrorGuidance.ensureGuidance(
                    "WEBSITE_DELIVERY_CONFIRM_FAILED",
                    normalizeMessage(failureMessage, fallback));
            orderService.updateLastError(
                    orderId, "WEBSITE_DELIVERY_CONFIRM_FAILED", errorMessage);
            appendEvent(
                    order,
                    "delivery_confirmation_failed",
                    errorMessage,
                    Map.of(
                            "stage", "execute",
                            "request_id", requestId,
                            "machine_id", machineId,
                            "chat_sent", chatSent,
                            "chat_closed", chatClosed,
                            "delivery_confirmed", deliveryConfirmed));
            return;
        }

        manualOrderStatusService.complete(orderId);
        orderService.updateLastError(orderId, null, null);
        Map<String, Object> completionPayload = new LinkedHashMap<>();
        completionPayload.put("request_id", requestId);
        completionPayload.put("machine_id", machineId);
        completionPayload.put("screenshot_path", order.getGameTradeScreenshot());
        for (String key : new String[]{
                "website_stage", "website_status", "already_completed"}) {
            if (safeDetails.containsKey(key) && safeDetails.get(key) != null) {
                completionPayload.put(key, safeDetails.get(key));
            }
        }
        appendEvent(
                order,
                "delivery_confirmation_completed",
                normalizeMessage(
                        message,
                        "截图已发送，聊天页已关闭，网站商品交付已确认"),
                completionPayload,
                "wait_web_confirm",
                "completed");
    }

    private void appendEvent(
            GameItemOrder order,
            String eventType,
            String message,
            Map<String, Object> payload) {
        appendEvent(
                order,
                eventType,
                message,
                payload,
                order.getDeliveryStatus(),
                order.getDeliveryStatus());
    }

    private void appendEvent(
            GameItemOrder order,
            String eventType,
            String message,
            Map<String, Object> payload,
            String fromStatus,
            String toStatus) {
        try {
            TradeEvent event = new TradeEvent();
            event.setOrderId(order.getId());
            event.setAssignmentId(order.getAssignmentId());
            event.setEventType(eventType);
            event.setFromStatus(fromStatus);
            event.setToStatus(toStatus);
            event.setMessage(message);
            event.setPayload(payload);
            tradeEventService.save(event);
        } catch (Exception e) {
            log.warn(
                    "[DeliveryConfirmation] 事件记录失败 order_id={} type={}: {}",
                    order.getId(), eventType, e.getMessage());
        }
    }

    private static String normalizeMessage(String value, String fallback) {
        String result = value == null ? "" : value.strip();
        if (result.isBlank()) {
            result = fallback;
        }
        return result.substring(0, Math.min(300, result.length()));
    }
}
