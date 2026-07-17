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
    WAITING_ASSIGNMENT("waiting_assignment", "pending", "offer被拒/过期，待重新指派"),
    SUSPENDED("suspended", "pending", "交易完成/取消/失败");

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
        KEY_MAP = Map.of("detected|pending", DETECTED,
                "greeting|pending", GREETING,
                "greeting|abnormal", GREETING_ABNORMAL,
                "offered|pending", OFFERED,
                "assigned|pending", ASSIGNED,
                "waiting_assignment|pending", WAITING_ASSIGNMENT,
                "suspended|pending", SUSPENDED);
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
