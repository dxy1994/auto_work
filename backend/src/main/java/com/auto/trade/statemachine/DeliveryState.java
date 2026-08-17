package com.auto.trade.statemachine;

import lombok.Getter;

import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;

/**
 * 订单交付联合状态：delivery_status + status 的组合枚举。
 */
@Getter
public enum DeliveryState {

    DETECTED("detected", "pending", "订单刚入库"),
    GREETING("greeting", "pending", "等待/正在招呼"),
    GREETING_ABNORMAL("greeting", "abnormal", "无话术或无子订单，等人工处理"),
    OFFERED("offered", "pending", "已发送交易指派"),
    ASSIGNED("assigned", "pending", "Worker已接受，执行中"),
    QUEUED("queued", "pending", "交易机器忙碌，按订单时间排队"),
    WAITING_ASSIGNMENT("waiting_assignment", "pending", "offer被拒/过期，待重新指派"),
    WAIT_WEB_CONFIRM("wait_web_confirm", "processing", "游戏交易完成，等待网站确认"),
    COMPLETED("completed", "completed", "游戏内交易已完成"),
    CANCELLED("cancelled", "cancelled", "订单已取消"),
    REVIEW_REQUIRED("review_required", "pending", "交易结果不确定，需要人工复核"),
    SUSPENDED("suspended", "pending", "交易取消或不可自动重试，等人工处理");

    private final String deliveryStatus;
    private final String orderStatus;
    private final String description;

    /** 联合键：deliveryStatus + "|" + orderStatus */
    private final String key;

    private static final Map<String, DeliveryState> KEY_MAP;

    DeliveryState(String deliveryStatus, String orderStatus, String description) {
        this.deliveryStatus = deliveryStatus;
        this.orderStatus = orderStatus;
        this.description = description;
        this.key = deliveryStatus + "|" + orderStatus;
    }

    static {
        KEY_MAP = Map.ofEntries(
                Map.entry("detected|pending", DETECTED),
                Map.entry("greeting|pending", GREETING),
                Map.entry("greeting|abnormal", GREETING_ABNORMAL),
                Map.entry("offered|pending", OFFERED),
                Map.entry("assigned|pending", ASSIGNED),
                Map.entry("queued|pending", QUEUED),
                Map.entry("waiting_assignment|pending", WAITING_ASSIGNMENT),
                Map.entry("wait_web_confirm|processing", WAIT_WEB_CONFIRM),
                Map.entry("completed|completed", COMPLETED),
                Map.entry("cancelled|cancelled", CANCELLED),
                Map.entry("review_required|pending", REVIEW_REQUIRED),
                Map.entry("suspended|pending", SUSPENDED));
    }

    /** 根据 delivery_status 和 status 反查联合状态。 */
    public static DeliveryState from(String deliveryStatus, String orderStatus) {
        DeliveryState state = KEY_MAP.get((deliveryStatus == null ? "" : deliveryStatus)
                + "|" + (orderStatus == null ? "" : orderStatus));
        if (state == null) {
            throw new IllegalStateException(
                    "未知的交付状态组合: deliveryStatus=" + deliveryStatus + ", orderStatus=" + orderStatus);
        }
        return state;
    }
}
