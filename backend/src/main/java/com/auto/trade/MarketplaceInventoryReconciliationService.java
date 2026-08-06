package com.auto.trade;

import com.auto.common.ApiException;
import com.auto.entity.GameRegionInventory;
import com.auto.entity.PlatformSalesProduct;
import com.auto.entity.SystemAlert;
import com.auto.service.GameRegionInventoryService;
import com.auto.service.InventoryChangeLogService;
import com.auto.service.PlatformSalesProductService;
import com.auto.service.SystemAlertService;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.OptionalLong;

/** 核对平台在售库存与系统大区库存，并处理告警及人工同步。 */
@Service
public class MarketplaceInventoryReconciliationService {

    private static final String ALERT_TYPE = "inventory_mismatch";
    // 临时关闭库存核对系统通知；恢复时改为 true 即可。
    private static final boolean INVENTORY_ALERTS_ENABLED = false;

    private final PlatformSalesProductService productService;
    private final GameRegionInventoryService inventoryService;
    private final InventoryChangeLogService changeLogService;
    private final SystemAlertService alertService;

    public MarketplaceInventoryReconciliationService(
            PlatformSalesProductService productService,
            GameRegionInventoryService inventoryService,
            InventoryChangeLogService changeLogService,
            SystemAlertService alertService) {
        this.productService = productService;
        this.inventoryService = inventoryService;
        this.changeLogService = changeLogService;
        this.alertService = alertService;
    }

    /** 每次完整快照落库后核对；相同且未变化的异常不会重复刷新告警。 */
    public void reconcileSnapshotProduct(PlatformSalesProduct product) {
        reconcileSnapshotProducts(List.of(product));
    }

    /** 批量核对完整快照，相同大区物品只查询一次系统库存。 */
    public void reconcileSnapshotProducts(List<PlatformSalesProduct> products) {
        Map<String, GameRegionInventory> inventories = new HashMap<>();
        for (PlatformSalesProduct product : products) {
            Comparison comparison = compare(
                    product, inventoryFor(product, inventories));
            String sourceKey = alertSourceKey(product);
            if (!INVENTORY_ALERTS_ENABLED) {
                // 同时关闭此前已生成的库存通知，避免前端继续展示旧提醒。
                alertService.dismissBySourceKey(sourceKey);
                continue;
            }
            if ("matched".equals(comparison.status())) {
                alertService.dismissBySourceKey(sourceKey);
            } else if ("mismatch".equals(comparison.status())) {
                ensureMismatchAlert(product, comparison, sourceKey);
            } else if ("inventory_missing".equals(comparison.status())) {
                ensureMissingInventoryAlert(product, comparison, sourceKey);
            } else if ("not_matched".equals(comparison.status())) {
                alertService.dismissBySourceKey(sourceKey);
            }
        }
    }

    /** 商品从完整快照中消失时，关闭其遗留库存告警。 */
    public void dismissRemovedProduct(PlatformSalesProduct product) {
        alertService.dismissBySourceKey(alertSourceKey(product));
    }

    /** 为查询结果附加解析库存、系统库存和比对状态，不写数据库。 */
    public void enrich(List<PlatformSalesProduct> products) {
        if (products == null || products.isEmpty()) {
            return;
        }
        Map<String, GameRegionInventory> inventories = new HashMap<>();
        for (PlatformSalesProduct product : products) {
            GameRegionInventory inventory = inventoryFor(product, inventories);
            applyComparison(product, compare(product, inventory));
        }
    }

    /** 用平台抓取到的库存覆盖系统大区库存，并写入库存审计日志。 */
    @Transactional
    public PlatformSalesProduct syncInventoryFromPlatform(int productId) {
        PlatformSalesProduct product = productService.getById(productId);
        if (product == null) {
            throw ApiException.notFound("在售商品不存在");
        }
        GameRegionInventory inventory = inventoryFor(product);
        Comparison comparison = compare(product, inventory);
        if ("not_matched".equals(comparison.status())) {
            throw ApiException.badRequest("只有完整解析的在售商品可以同步库存");
        }
        if ("quantity_unavailable".equals(comparison.status())) {
            throw ApiException.badRequest("平台库存数量无法解析，不能同步");
        }
        if (inventory == null) {
            throw ApiException.badRequest("未找到该大区和物品对应的系统库存");
        }

        long platformStock = comparison.platformStock();
        long stockBefore = inventory.getStock() == null ? 0L : inventory.getStock();
        if (stockBefore != platformStock) {
            inventory.setStock(platformStock);
            inventoryService.updateById(inventory);
            changeLogService.logSystemSync(
                    inventory,
                    stockBefore,
                    "在售商品 #" + product.getPlatformProductId()
                            + " 平台库存同步（范围数量按上限）",
                    "admin");
        }
        alertService.dismissBySourceKey(alertSourceKey(product));
        applyComparison(product, compare(product, inventory));
        return product;
    }

    private void ensureMismatchAlert(
            PlatformSalesProduct product, Comparison comparison,
            String sourceKey) {
        String title = "在售商品库存不一致";
        String message = productIdentity(product)
                + "的平台库存为 " + comparison.platformStock()
                + "，系统库存为 " + comparison.systemStock()
                + "。请在“平台在售商品”列表核对；需要以平台抓取值覆盖系统库存时，"
                + "点击“同步库存”。范围数量已按最高值比对。";
        openIfChanged(product, sourceKey, title, message);
    }

    private void ensureMissingInventoryAlert(
            PlatformSalesProduct product, Comparison comparison,
            String sourceKey) {
        String title = "在售商品缺少系统库存";
        String message = productIdentity(product)
                + "的平台库存已解析为 " + comparison.platformStock()
                + "，但未找到对应的大区物品库存，无法完成核对。"
                + "请先检查大区库存配置。范围数量已按最高值解析。";
        openIfChanged(product, sourceKey, title, message);
    }

    private void openIfChanged(
            PlatformSalesProduct product, String sourceKey,
            String title, String message) {
        SystemAlert existing = alertService.getOne(
                new LambdaQueryWrapper<SystemAlert>()
                        .eq(SystemAlert::getSourceKey, sourceKey)
                        .eq(SystemAlert::getStatus, "open")
                        .orderByDesc(SystemAlert::getId)
                        .last("LIMIT 1"), false);
        if (existing != null
                && Objects.equals(existing.getTitle(), title)
                && Objects.equals(existing.getMessage(), message)) {
            return;
        }
        alertService.openOrRefresh(
                ALERT_TYPE,
                sourceKey,
                null,
                product.getPlatformAccountId(),
                "warning",
                title,
                message);
    }

    private GameRegionInventory inventoryFor(PlatformSalesProduct product) {
        if (!isResolved(product)) {
            return null;
        }
        return inventoryService.findByRegionIdAndItemId(
                product.getRegionId(), product.getGameItemId());
    }

    private GameRegionInventory inventoryFor(
            PlatformSalesProduct product,
            Map<String, GameRegionInventory> inventories) {
        if (!isResolved(product)) {
            return null;
        }
        String key = inventoryKey(
                product.getRegionId(), product.getGameItemId());
        if (!inventories.containsKey(key)) {
            inventories.put(key, inventoryService.findByRegionIdAndItemId(
                    product.getRegionId(), product.getGameItemId()));
        }
        return inventories.get(key);
    }

    private Comparison compare(
            PlatformSalesProduct product, GameRegionInventory inventory) {
        if (!isResolved(product)) {
            return new Comparison("not_matched", null, null, null);
        }
        OptionalLong parsed = MarketplaceQuantityParser.parseMaximum(
                product.getQuantityText());
        if (parsed.isEmpty()) {
            return new Comparison("quantity_unavailable", null,
                    inventory == null ? null : inventory.getStock(), inventory);
        }
        long platformStock = parsed.getAsLong();
        if (inventory == null) {
            return new Comparison("inventory_missing", platformStock, null, null);
        }
        long systemStock = inventory.getStock() == null ? 0L : inventory.getStock();
        return new Comparison(
                platformStock == systemStock ? "matched" : "mismatch",
                platformStock,
                systemStock,
                inventory);
    }

    private void applyComparison(
            PlatformSalesProduct product, Comparison comparison) {
        product.setParsedQuantity(comparison.platformStock());
        product.setInventoryComparisonStatus(comparison.status());
        GameRegionInventory inventory = comparison.inventory();
        product.setInventoryId(inventory == null ? null : inventory.getId());
        product.setInventoryStock(comparison.systemStock());
    }

    private static boolean isResolved(PlatformSalesProduct product) {
        return product != null
                && "matched".equals(product.getParseStatus())
                && product.getRegionId() != null
                && product.getGameItemId() != null;
    }

    private static String productIdentity(PlatformSalesProduct product) {
        String item = product.getParsedItemName() == null
                || product.getParsedItemName().isBlank()
                ? "未知物品" : product.getParsedItemName();
        String region = product.getRegionName() == null
                || product.getRegionName().isBlank()
                ? "未知大区" : product.getRegionName();
        return "平台商品 #" + product.getPlatformProductId()
                + "（" + region + " / " + item + "）";
    }

    private static String alertSourceKey(PlatformSalesProduct product) {
        return "sales-product:" + product.getPlatformAccountId()
                + ":" + product.getPlatformProductId() + ":inventory";
    }

    private static String inventoryKey(Integer regionId, Integer itemId) {
        return regionId == null || itemId == null
                ? "" : regionId + ":" + itemId;
    }

    private record Comparison(
            String status,
            Long platformStock,
            Long systemStock,
            GameRegionInventory inventory) {
    }
}
