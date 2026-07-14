package com.auto.trade;

import java.util.EnumSet;
import java.util.Set;

/** 自动交易交付状态及其允许的有向迁移。 */
public enum TradeDeliveryStatus {
    DETECTED,
    VALIDATED,
    WAITING_ASSIGNMENT,
    OFFERED,
    ASSIGNED,
    PRECHECKING,
    WAITING_BUYER,
    VERIFYING_BUYER,
    STAGING_ASSET,
    REVIEWING,
    CONFIRMING,
    GAME_DELIVERED,
    WEBSITE_CONFIRMING,
    COMPLETED,
    SUSPENDED,
    CANCELLED;

    public boolean canMoveTo(TradeDeliveryStatus target) {
        return target != null && allowedTargets().contains(target);
    }

    public void requireMoveTo(TradeDeliveryStatus target) {
        if (!canMoveTo(target)) {
            throw new IllegalStateException("illegal trade transition: " + this + " -> " + target);
        }
    }

    private Set<TradeDeliveryStatus> allowedTargets() {
        return switch (this) {
            case DETECTED -> EnumSet.of(VALIDATED, SUSPENDED, CANCELLED);
            case VALIDATED -> EnumSet.of(WAITING_ASSIGNMENT, SUSPENDED, CANCELLED);
            case WAITING_ASSIGNMENT -> EnumSet.of(OFFERED, SUSPENDED, CANCELLED);
            case OFFERED -> EnumSet.of(WAITING_ASSIGNMENT, ASSIGNED, SUSPENDED, CANCELLED);
            case ASSIGNED -> EnumSet.of(PRECHECKING, SUSPENDED, CANCELLED);
            case PRECHECKING -> EnumSet.of(WAITING_BUYER, SUSPENDED);
            case WAITING_BUYER -> EnumSet.of(VERIFYING_BUYER, SUSPENDED);
            case VERIFYING_BUYER -> EnumSet.of(WAITING_BUYER, STAGING_ASSET, SUSPENDED);
            case STAGING_ASSET -> EnumSet.of(REVIEWING, SUSPENDED);
            case REVIEWING -> EnumSet.of(CONFIRMING, SUSPENDED);
            case CONFIRMING -> EnumSet.of(GAME_DELIVERED, SUSPENDED);
            case GAME_DELIVERED -> EnumSet.of(WEBSITE_CONFIRMING, SUSPENDED);
            case WEBSITE_CONFIRMING -> EnumSet.of(GAME_DELIVERED, COMPLETED, SUSPENDED);
            case SUSPENDED -> EnumSet.of(WAITING_ASSIGNMENT, GAME_DELIVERED, CANCELLED);
            case COMPLETED, CANCELLED -> EnumSet.noneOf(TradeDeliveryStatus.class);
        };
    }
}
