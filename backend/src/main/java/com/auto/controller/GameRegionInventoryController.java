package com.auto.controller;

import com.auto.common.ApiException;
import com.auto.common.PageRequests;
import com.auto.entity.GameRegionInventory;
import com.auto.entity.GameRegionInventoryShopPrice;
import com.auto.entity.InventoryChangeLog;
import com.auto.service.GameRegionInventoryService;
import com.auto.service.GameRegionInventoryShopPriceService;
import com.auto.service.InventoryChangeLogService;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/** 大区物品库存管理。 */
@RestController
@RequestMapping("/api/region-inventories")
public class GameRegionInventoryController {

    private static final int MAX_BATCH_SIZE = 500;

    private final GameRegionInventoryService inventoryService;
    private final GameRegionInventoryShopPriceService shopPriceService;
    private final InventoryChangeLogService changeLogService;

    public GameRegionInventoryController(GameRegionInventoryService inventoryService,
                                         GameRegionInventoryShopPriceService shopPriceService,
                                         InventoryChangeLogService changeLogService) {
        this.inventoryService = inventoryService;
        this.shopPriceService = shopPriceService;
        this.changeLogService = changeLogService;
    }

    @GetMapping
    public Map<String, Object> list(
            @RequestParam(name = "game_id", required = false) Integer gameId,
            @RequestParam(name = "region_id", required = false) Integer regionId,
            @RequestParam(name = "item_id", required = false) Integer itemId,
            @RequestParam(name = "has_stock", required = false) Integer hasStock,
            @RequestParam(name = "keyword", required = false) String keyword,
            @RequestParam(name = "account_id", required = false) Integer accountId,
            @RequestParam(name = "page", defaultValue = "1") int page,
            @RequestParam(name = "page_size", defaultValue = "50") int pageSize) {
        Page<Map<String, Object>> pageObj = PageRequests.of(page, pageSize);
        IPage<Map<String, Object>> result = inventoryService.searchWithItem(gameId, regionId, itemId, hasStock, keyword, accountId, pageObj);
        return Map.of("total", result.getTotal(), "items", result.getRecords());
    }

    @GetMapping("/all")
    public List<Map<String, Object>> listAll(
            @RequestParam(name = "game_id", required = false) Integer gameId,
            @RequestParam(name = "region_id", required = false) Integer regionId,
            @RequestParam(name = "account_id", required = false) Integer accountId) {
        return inventoryService.findAllWithItem(gameId, regionId, accountId);
    }

    @PutMapping("/batch/update")
    @Transactional
    public List<GameRegionInventory> batchUpdate(@RequestBody Map<String, Object> payload) {
        Object rawItems = payload.get("items");
        if (!(rawItems instanceof List<?> items) || items.isEmpty()) {
            throw ApiException.badRequest("items 不能为空");
        }
        if (items.size() > MAX_BATCH_SIZE) {
            throw ApiException.badRequest("单次最多更新 " + MAX_BATCH_SIZE + " 条");
        }
        Map<Integer, BigDecimal> maxFluctuationById = new LinkedHashMap<>();
        Map<Integer, BigDecimal> maxFluctuationRateById = new LinkedHashMap<>();
        for (Object raw : items) {
            if (!(raw instanceof Map<?, ?> item)) {
                throw ApiException.badRequest("items 元素格式错误");
            }
            Integer id = toInt(item.get("id"));
            if (id == null) throw ApiException.badRequest("items 元素缺少 id");
            // 拒绝系统管理字段，仅允许风控参数
            if (item.containsKey("stock") || item.containsKey("purchase_price")) {
                throw ApiException.badRequest("库存数量和进货价由系统管理，不可手动修改");
            }
            boolean hasField = false;
            BigDecimal maxFluctuation = toBigDecimal(item.get("max_fluctuation"));
            if (maxFluctuation != null) { maxFluctuationById.put(id, maxFluctuation); hasField = true; }
            BigDecimal maxFluctuationRate = toBigDecimal(item.get("max_fluctuation_rate"));
            if (maxFluctuationRate != null) { maxFluctuationRateById.put(id, maxFluctuationRate); hasField = true; }
            if (!hasField) throw ApiException.badRequest("items 元素缺少可更新字段");
        }
        Set<Integer> allIds = new LinkedHashSet<>();
        allIds.addAll(maxFluctuationById.keySet());
        allIds.addAll(maxFluctuationRateById.keySet());
        List<Integer> ids = new ArrayList<>(allIds);
        List<GameRegionInventory> existing = inventoryService.listByIds(ids);
        if (existing.size() != ids.size()) {
            throw ApiException.notFound("部分库存记录不存在");
        }
        List<GameRegionInventory> ordered = new ArrayList<>();
        for (GameRegionInventory inv : existing) {
            Integer invId = inv.getId();
            if (maxFluctuationById.containsKey(invId)) {
                BigDecimal oldVal = inv.getMaxFluctuation();
                BigDecimal newVal = maxFluctuationById.get(invId);
                inv.setMaxFluctuation(newVal);
                changeLogService.logFluctuationUpdate(inv, "max_fluctuation",
                        oldVal != null ? oldVal.toPlainString() : "null",
                        newVal != null ? newVal.toPlainString() : "null", "admin");
            }
            if (maxFluctuationRateById.containsKey(invId)) {
                BigDecimal oldVal = inv.getMaxFluctuationRate();
                BigDecimal newVal = maxFluctuationRateById.get(invId);
                inv.setMaxFluctuationRate(newVal);
                changeLogService.logFluctuationUpdate(inv, "max_fluctuation_rate",
                        oldVal != null ? oldVal.toPlainString() : "null",
                        newVal != null ? newVal.toPlainString() : "null", "admin");
            }
            ordered.add(inv);
        }
        inventoryService.updateBatchById(ordered);
        return ordered;
    }

    @GetMapping("/{inventoryId}")
    public GameRegionInventory get(@PathVariable Integer inventoryId) {
        GameRegionInventory inv = inventoryService.getById(inventoryId);
        if (inv == null) throw ApiException.notFound("库存记录不存在");
        return inv;
    }

    @PutMapping("/{inventoryId}")
    public GameRegionInventory update(@PathVariable Integer inventoryId, @RequestBody Map<String, Object> payload) {
        GameRegionInventory inv = inventoryService.getById(inventoryId);
        if (inv == null) throw ApiException.notFound("库存记录不存在");
        // 拒绝系统管理字段
        if (payload.containsKey("stock") || payload.containsKey("purchase_price")) {
            throw ApiException.badRequest("库存数量和进货价由系统管理，不可手动修改");
        }
        BigDecimal maxFluctuation = toBigDecimal(payload.get("max_fluctuation"));
        if (maxFluctuation != null) {
            BigDecimal oldVal = inv.getMaxFluctuation();
            inv.setMaxFluctuation(maxFluctuation);
            changeLogService.logFluctuationUpdate(inv, "max_fluctuation",
                    oldVal != null ? oldVal.toPlainString() : "null",
                    maxFluctuation.toPlainString(), "admin");
        }
        BigDecimal maxFluctuationRate = toBigDecimal(payload.get("max_fluctuation_rate"));
        if (maxFluctuationRate != null) {
            BigDecimal oldVal = inv.getMaxFluctuationRate();
            inv.setMaxFluctuationRate(maxFluctuationRate);
            changeLogService.logFluctuationUpdate(inv, "max_fluctuation_rate",
                    oldVal != null ? oldVal.toPlainString() : "null",
                    maxFluctuationRate.toPlainString(), "admin");
        }
        inventoryService.updateById(inv);
        return inv;
    }

    // ── 入库 ──

    @PostMapping("/stock/in")
    @Transactional
    public Map<String, Object> stockIn(@RequestBody Map<String, Object> payload) {
        Integer inventoryId = toInt(payload.get("inventory_id"));
        if (inventoryId == null) throw ApiException.badRequest("inventory_id 不能为空");
        Long quantity = toLong(payload.get("quantity"));
        if (quantity == null || quantity <= 0) throw ApiException.badRequest("入库数量必须大于 0");
        BigDecimal unitPrice = toBigDecimal(payload.get("unit_price"));
        if (unitPrice == null || unitPrice.signum() < 0) throw ApiException.badRequest("入库单价不能为空且不能为负数");

        GameRegionInventory inv = inventoryService.getById(inventoryId);
        if (inv == null) throw ApiException.notFound("库存记录不存在");

        // 记录旧值
        long oldStock = inv.getStock() != null ? inv.getStock() : 0L;
        BigDecimal oldAvg = inv.getPurchasePrice() != null ? inv.getPurchasePrice() : BigDecimal.ZERO;

        // 计算新库存和加权均价
        long newStock;
        try {
            newStock = Math.addExact(oldStock, quantity);
        } catch (ArithmeticException e) {
            throw ApiException.badRequest("入库后库存数量超出 long 类型范围");
        }
        BigDecimal totalOldCost = oldAvg.multiply(BigDecimal.valueOf(oldStock));
        BigDecimal totalNewCost = unitPrice.multiply(BigDecimal.valueOf(quantity));
        BigDecimal newAvg = totalOldCost.add(totalNewCost)
                .divide(BigDecimal.valueOf(newStock), 4, RoundingMode.HALF_UP);

        inv.setStock(newStock);
        inv.setPurchasePrice(newAvg);
        inventoryService.updateById(inv);

        // 写审计日志
        changeLogService.logStockIn(inv, quantity, unitPrice, oldAvg, newAvg, "admin");

        return Map.of("id", inv.getId(), "stock", newStock, "purchase_price", newAvg);
    }

    // ── 出库 ──

    @PostMapping("/stock/out")
    @Transactional
    public Map<String, Object> stockOut(@RequestBody Map<String, Object> payload) {
        Integer inventoryId = toInt(payload.get("inventory_id"));
        if (inventoryId == null) throw ApiException.badRequest("inventory_id 不能为空");
        Long quantity = toLong(payload.get("quantity"));
        if (quantity == null || quantity <= 0) throw ApiException.badRequest("出库数量必须大于 0");
        String reason = payload.get("reason") instanceof String s && !s.isBlank() ? s.trim() : null;
        if (reason == null) throw ApiException.badRequest("出库原因不能为空");

        GameRegionInventory inv = inventoryService.getById(inventoryId);
        if (inv == null) throw ApiException.notFound("库存记录不存在");
        if (inv.getStock() < quantity) {
            throw ApiException.badRequest("库存不足，当前库存: " + inv.getStock() + "，出库数量: " + quantity);
        }

        long newStock = inv.getStock() - quantity;
        inv.setStock(newStock);
        // 出库均价不变
        inventoryService.updateById(inv);

        changeLogService.logStockOut(inv, quantity, reason, "admin");

        return Map.of("id", inv.getId(), "stock", newStock,
                "purchase_price", inv.getPurchasePrice());
    }

    // ── 商铺定价查询（按库存ID）──

    @GetMapping("/{inventoryId}/shop-prices")
    public List<GameRegionInventoryShopPrice> shopPrices(@PathVariable Integer inventoryId) {
        GameRegionInventory inv = inventoryService.getById(inventoryId);
        if (inv == null) throw ApiException.notFound("库存记录不存在");
        return shopPriceService.findByInventoryId(inventoryId);
    }

    // ── 变更记录查询 ──

    @GetMapping("/{inventoryId}/change-logs")
    public List<InventoryChangeLog> changeLogs(@PathVariable Integer inventoryId) {
        GameRegionInventory inv = inventoryService.getById(inventoryId);
        if (inv == null) throw ApiException.notFound("库存记录不存在");
        return changeLogService.findByInventoryId(inventoryId);
    }

    // ── 商铺定价批量更新 ──

    @PutMapping("/shop-prices/batch")
    @Transactional
    public List<Map<String, Object>> batchUpdateShopPrices(@RequestBody Map<String, Object> payload) {
        @SuppressWarnings("unchecked")
        List<Map<String, Object>> items = (List<Map<String, Object>>) payload.get("items");
        if (items == null || items.isEmpty()) {
            throw ApiException.badRequest("items 不能为空");
        }
        if (items.size() > MAX_BATCH_SIZE) {
            throw ApiException.badRequest("单次最多更新 " + MAX_BATCH_SIZE + " 条");
        }

        List<Map<String, Object>> results = new ArrayList<>();
        for (Map<String, Object> item : items) {
            Integer shopPriceId = toInt(item.get("shop_price_id"));
            Integer inventoryId = toInt(item.get("inventory_id"));
            Integer accountId = toInt(item.get("account_id"));

            GameRegionInventoryShopPrice sp;
            if (shopPriceId != null) {
                sp = shopPriceService.getById(shopPriceId);
                if (sp == null) throw ApiException.notFound("商铺定价记录不存在: " + shopPriceId);
            } else if (inventoryId != null && accountId != null) {
                sp = shopPriceService.findByInventoryIdAndAccountId(inventoryId, accountId);
                if (sp == null) throw ApiException.notFound("商铺定价记录不存在: inv=" + inventoryId + " acc=" + accountId);
            } else {
                throw ApiException.badRequest("需要 shop_price_id 或 (inventory_id + account_id)");
            }

            BigDecimal sellingPrice = toBigDecimal(item.get("selling_price"));
            BigDecimal minPrice = toBigDecimal(item.get("min_selling_price"));
            BigDecimal maxPrice = toBigDecimal(item.get("max_selling_price"));

            boolean updated = false;
            if (sellingPrice != null) { sp.setSellingPrice(sellingPrice); updated = true; }
            if (minPrice != null) { sp.setMinSellingPrice(minPrice); updated = true; }
            if (maxPrice != null) { sp.setMaxSellingPrice(maxPrice); updated = true; }

            if (updated) {
                shopPriceService.updateById(sp);
            }

            Map<String, Object> result = new LinkedHashMap<>();
            result.put("shop_price_id", sp.getId());
            result.put("inventory_id", sp.getInventoryId());
            result.put("account_id", sp.getAccountId());
            result.put("selling_price", sp.getSellingPrice());
            result.put("min_selling_price", sp.getMinSellingPrice());
            result.put("max_selling_price", sp.getMaxSellingPrice());
            results.add(result);
        }
        return results;
    }

    private Integer toInt(Object value) {
        if (value == null) return null;
        if (value instanceof Boolean) return null;
        if (value instanceof Number n) return n.intValue();
        if (value instanceof String s) {
            if (s.isBlank()) return null;
            try {
                return Integer.parseInt(s.trim());
            } catch (NumberFormatException e) {
                throw ApiException.badRequest("无效的数字: " + s);
            }
        }
        throw ApiException.badRequest("无效的数字类型");
    }

    private Long toLong(Object value) {
        if (value == null) return null;
        if (value instanceof Boolean) return null;
        if (value instanceof Number n) {
            try {
                return new BigDecimal(n.toString()).longValueExact();
            } catch (ArithmeticException | NumberFormatException e) {
                throw ApiException.badRequest("无效的长整数: " + value);
            }
        }
        if (value instanceof String s) {
            if (s.isBlank()) return null;
            try {
                return Long.parseLong(s.trim());
            } catch (NumberFormatException e) {
                throw ApiException.badRequest("无效的长整数: " + s);
            }
        }
        throw ApiException.badRequest("无效的数字类型");
    }

    private BigDecimal toBigDecimal(Object value) {
        if (value == null) return null;
        if (value instanceof Boolean) return null;
        if (value instanceof BigDecimal b) return b;
        if (value instanceof Number n) return BigDecimal.valueOf(n.doubleValue());
        if (value instanceof String s) {
            if (s.isBlank()) return null;
            try {
                return new BigDecimal(s.trim());
            } catch (NumberFormatException e) {
                throw ApiException.badRequest("无效的数字: " + s);
            }
        }
        throw ApiException.badRequest("无效的数字类型");
    }
}
