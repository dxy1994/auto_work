package com.auto.trade;

import java.util.HashSet;
import java.util.List;
import java.util.Set;

/** Worker 上报的某个平台账号完整在售商品快照。 */
public record SalesProductsSnapshotMessage(
        String platform,
        List<SalesProductObservation> products) {

    private static final Set<String> PLATFORMS =
            Set.of("itemmania", "barotem", "itembay");
    private static final int MAX_PRODUCTS = 10_000;

    public SalesProductsSnapshotMessage {
        platform = platform == null ? "" : platform.trim().toLowerCase();
        if (!PLATFORMS.contains(platform)) {
            throw new IllegalArgumentException("unsupported platform");
        }
        products = products == null ? List.of() : List.copyOf(products);
        if (products.size() > MAX_PRODUCTS) {
            throw new IllegalArgumentException("too many products");
        }
        Set<String> ids = new HashSet<>();
        for (SalesProductObservation product : products) {
            if (product == null) {
                throw new IllegalArgumentException("product is required");
            }
            if (!ids.add(product.platformProductId())) {
                throw new IllegalArgumentException(
                        "duplicate platform_product_id: "
                                + product.platformProductId());
            }
        }
    }
}
