package com.auto.trade;

import com.auto.entity.GameItemOrder;
import com.auto.entity.TradeAssignment;
import com.auto.entity.TradeEvent;
import com.auto.service.TradeEventService;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.LinkedHashMap;
import java.util.Map;

/** 持久化买家人工审核结果，供订单日志和总控通知中心共同使用。 */
@Service
public class BuyerReviewAuditService {

    private final TradeEventService tradeEventService;

    public BuyerReviewAuditService(TradeEventService tradeEventService) {
        this.tradeEventService = tradeEventService;
    }

    /** 记录人工拒绝；待审核提醒由 pending 审核请求本身提供，拒绝后不再新增通知。 */
    @Transactional
    public void recordRejected(GameItemOrder order, TradeAssignment assignment) {
        String reviewId = requiredText(assignment.getBuyerReviewId(), "审核请求 ID");
        String assignmentId = requiredText(assignment.getAssignmentId(), "交易指派 ID");
        String orderLabel = hasText(order.getOrderNo())
                ? "订单 " + order.getOrderNo() + "（ID " + order.getId() + "）"
                : "订单 ID " + order.getId();
        String expectedBuyer = firstText(assignment.getExpectedBuyerName(),
                order.getBuyerCharacter(), "未提供");
        String observedBuyer = firstText(assignment.getObservedBuyerName(), "未识别");
        String machineLabel = assignment.getMachineId() == null
                ? "未知机器" : "机器#" + assignment.getMachineId();
        String message = orderLabel + "，" + machineLabel
                + "；订单玩家=" + expectedBuyer
                + "，识别玩家=" + observedBuyer
                + "。人工已拒绝，已通知 Worker 取消当前交易请求。";

        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("decision", "rejected");
        payload.put("review_id", reviewId);
        payload.put("assignment_id", assignmentId);
        payload.put("machine_id", assignment.getMachineId());
        payload.put("game_account_id", assignment.getGameAccountId());
        payload.put("expected_buyer_name", expectedBuyer);
        payload.put("observed_buyer_name", observedBuyer);
        payload.put("buyer_ocr_confidence", assignment.getBuyerOcrConfidence());
        payload.put("decided_at", assignment.getBuyerReviewDecidedAt());

        TradeEvent event = new TradeEvent();
        event.setOrderId(order.getId());
        event.setAssignmentId(assignmentId);
        event.setEventType("buyer_review_rejected");
        event.setFromStatus(order.getDeliveryStatus());
        event.setToStatus(order.getDeliveryStatus());
        event.setMessage(message);
        event.setPayload(payload);
        event.setCreatedAt(LocalDateTime.now());
        tradeEventService.save(event);
    }

    private static String requiredText(String value, String fieldName) {
        if (!hasText(value)) {
            throw new IllegalStateException(fieldName + "不能为空");
        }
        return value.trim();
    }

    private static String firstText(String... values) {
        for (String value : values) {
            if (hasText(value)) {
                return value.trim();
            }
        }
        return "";
    }

    private static boolean hasText(String value) {
        return value != null && !value.isBlank();
    }
}
