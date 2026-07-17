package com.auto.trade.statemachine;

/** 状态转换定义：from + event → to + action。 */
public record Transition(
        DeliveryState from,
        DeliveryEvent event,
        DeliveryState to,
        TransitionAction action
) {
    /** 用于 Map 查找的复合键。 */
    public static String key(DeliveryState from, DeliveryEvent event) {
        return from.name() + ":" + event.name();
    }
}
