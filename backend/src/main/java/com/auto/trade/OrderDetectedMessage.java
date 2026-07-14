package com.auto.trade;

import java.math.BigDecimal;
import java.util.Set;

/** Worker 上报的平台无关订单字段。 */
public record OrderDetectedMessage(
        String platform,
        String sourceOrderNo,
        String regionExternalKey,
        String assetType,
        BigDecimal assetAmount,
        String buyerCharacter,
        String platformStatus,
        String rawTitle) {

    private static final Set<String> PLATFORMS = Set.of("itemmania", "barotem", "itembay");

    public OrderDetectedMessage {
        platform = required(platform, "platform").toLowerCase();
        if (!PLATFORMS.contains(platform)) {
            throw new IllegalArgumentException("unsupported platform");
        }
        sourceOrderNo = bounded(required(sourceOrderNo, "source_order_no"), 100, "source_order_no");
        regionExternalKey = bounded(required(regionExternalKey, "region_external_key"), 100,
                "region_external_key");
        assetType = required(assetType, "asset_type").toLowerCase();
        if (assetAmount == null || assetAmount.signum() <= 0) {
            throw new IllegalArgumentException("asset_amount must be positive");
        }
        buyerCharacter = bounded(required(buyerCharacter, "buyer_character"), 100, "buyer_character");
        platformStatus = bounded(required(platformStatus, "platform_status"), 32, "platform_status");
        rawTitle = bounded(rawTitle == null ? "" : rawTitle.trim(), 256, "raw_title");
    }

    private static String required(String value, String field) {
        String normalized = value == null ? "" : value.trim();
        if (normalized.isEmpty()) {
            throw new IllegalArgumentException(field + " is required");
        }
        return normalized;
    }

    private static String bounded(String value, int max, String field) {
        if (value.length() > max) {
            throw new IllegalArgumentException(field + " is too long");
        }
        return value;
    }
}
