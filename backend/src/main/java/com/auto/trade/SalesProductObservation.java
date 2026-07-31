package com.auto.trade;

/** Worker 从平台在售列表读取的一张商品卡片。 */
public record SalesProductObservation(
        String platformProductId,
        String platformItemType,
        String gameName,
        String regionName,
        String title,
        String quantityText,
        String priceText,
        String platformRegisteredAt) {

    public SalesProductObservation {
        platformProductId = bounded(
                required(platformProductId, "platform_product_id"),
                100, "platform_product_id");
        platformItemType = bounded(normalize(platformItemType),
                32, "platform_item_type");
        gameName = bounded(normalize(gameName), 100, "game_name");
        regionName = bounded(normalize(regionName), 100, "region_name");
        title = bounded(normalize(title), 500, "title");
        quantityText = bounded(normalize(quantityText),
                100, "quantity_text");
        priceText = bounded(normalize(priceText), 100, "price_text");
        platformRegisteredAt = bounded(normalize(platformRegisteredAt),
                64, "platform_registered_at");
    }

    private static String normalize(String value) {
        return value == null ? "" : value.trim();
    }

    private static String required(String value, String field) {
        String normalized = normalize(value);
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
