package com.auto.controller;

import com.auto.common.ApiException;
import com.auto.common.PageRequests;
import com.auto.entity.GameRegionItem;
import com.auto.service.GameRegionItemService;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/** 大区物品库存管理。 */
@RestController
@RequestMapping("/api/region-inventories")
public class GameRegionItemController {

    private static final int MAX_BATCH_SIZE = 500;

    private final GameRegionItemService inventoryService;

    public GameRegionItemController(GameRegionItemService inventoryService) {
        this.inventoryService = inventoryService;
    }

    @GetMapping
    public Map<String, Object> list(
            @RequestParam(name = "game_id", required = false) Integer gameId,
            @RequestParam(name = "region_id", required = false) Integer regionId,
            @RequestParam(name = "item_id", required = false) Integer itemId,
            @RequestParam(name = "has_stock", required = false) Integer hasStock,
            @RequestParam(name = "keyword", required = false) String keyword,
            @RequestParam(name = "page", defaultValue = "1") int page,
            @RequestParam(name = "page_size", defaultValue = "50") int pageSize) {
        Page<Map<String, Object>> pageObj = PageRequests.of(page, pageSize);
        IPage<Map<String, Object>> result = inventoryService.searchWithItem(gameId, regionId, itemId, hasStock, keyword, pageObj);
        return Map.of("total", result.getTotal(), "items", result.getRecords());
    }

    @GetMapping("/all")
    public List<Map<String, Object>> listAll(
            @RequestParam(name = "game_id", required = false) Integer gameId,
            @RequestParam(name = "region_id", required = false) Integer regionId) {
        return inventoryService.findAllWithItem(gameId, regionId);
    }

    @PutMapping("/batch/update")
    @Transactional
    public List<GameRegionItem> batchUpdate(@RequestBody Map<String, Object> payload) {
        Object rawItems = payload.get("items");
        if (!(rawItems instanceof List<?> items) || items.isEmpty()) {
            throw ApiException.badRequest("items 不能为空");
        }
        if (items.size() > MAX_BATCH_SIZE) {
            throw ApiException.badRequest("单次最多更新 " + MAX_BATCH_SIZE + " 条");
        }
        Map<Integer, Integer> stockById = new LinkedHashMap<>();
        Map<Integer, BigDecimal> purchasePriceById = new LinkedHashMap<>();
        Map<Integer, BigDecimal> sellingPriceById = new LinkedHashMap<>();
        Map<Integer, BigDecimal> minSellingPriceById = new LinkedHashMap<>();
        Map<Integer, BigDecimal> maxSellingPriceById = new LinkedHashMap<>();
        Map<Integer, BigDecimal> maxFluctuationById = new LinkedHashMap<>();
        Map<Integer, BigDecimal> maxFluctuationRateById = new LinkedHashMap<>();
        for (Object raw : items) {
            if (!(raw instanceof Map<?, ?> item)) {
                throw ApiException.badRequest("items 元素格式错误");
            }
            Integer id = toInt(item.get("id"));
            if (id == null) throw ApiException.badRequest("items 元素缺少 id");
            boolean hasField = false;
            Integer stock = toInt(item.get("stock"));
            if (stock != null) { validateStock(stock); stockById.put(id, stock); hasField = true; }
            BigDecimal purchasePrice = toBigDecimal(item.get("purchase_price")); if (purchasePrice != null) { purchasePriceById.put(id, purchasePrice); hasField = true; }
            BigDecimal sellingPrice = toBigDecimal(item.get("selling_price")); if (sellingPrice != null) { sellingPriceById.put(id, sellingPrice); hasField = true; }
            BigDecimal minSellingPrice = toBigDecimal(item.get("min_selling_price")); if (minSellingPrice != null) { minSellingPriceById.put(id, minSellingPrice); hasField = true; }
            BigDecimal maxSellingPrice = toBigDecimal(item.get("max_selling_price")); if (maxSellingPrice != null) { maxSellingPriceById.put(id, maxSellingPrice); hasField = true; }
            BigDecimal maxFluctuation = toBigDecimal(item.get("max_fluctuation")); if (maxFluctuation != null) { maxFluctuationById.put(id, maxFluctuation); hasField = true; }
            BigDecimal maxFluctuationRate = toBigDecimal(item.get("max_fluctuation_rate")); if (maxFluctuationRate != null) { maxFluctuationRateById.put(id, maxFluctuationRate); hasField = true; }
            if (!hasField) throw ApiException.badRequest("items 元素缺少可更新字段");
        }
        // 收集所有需要更新的 id
        Set<Integer> allIds = new LinkedHashSet<>();
        allIds.addAll(stockById.keySet());
        allIds.addAll(purchasePriceById.keySet());
        allIds.addAll(sellingPriceById.keySet());
        allIds.addAll(minSellingPriceById.keySet());
        allIds.addAll(maxSellingPriceById.keySet());
        allIds.addAll(maxFluctuationById.keySet());
        allIds.addAll(maxFluctuationRateById.keySet());
        List<Integer> ids = new ArrayList<>(allIds);
        List<GameRegionItem> existing = inventoryService.listByIds(ids);
        if (existing.size() != ids.size()) {
            throw ApiException.notFound("部分库存记录不存在");
        }
        List<GameRegionItem> ordered = new ArrayList<>();
        for (GameRegionItem inv : existing) {
            Integer invId = inv.getId();
            if (stockById.containsKey(invId)) inv.setStock(stockById.get(invId));
            if (purchasePriceById.containsKey(invId)) inv.setPurchasePrice(purchasePriceById.get(invId));
            if (sellingPriceById.containsKey(invId)) inv.setSellingPrice(sellingPriceById.get(invId));
            if (minSellingPriceById.containsKey(invId)) inv.setMinSellingPrice(minSellingPriceById.get(invId));
            if (maxSellingPriceById.containsKey(invId)) inv.setMaxSellingPrice(maxSellingPriceById.get(invId));
            if (maxFluctuationById.containsKey(invId)) inv.setMaxFluctuation(maxFluctuationById.get(invId));
            if (maxFluctuationRateById.containsKey(invId)) inv.setMaxFluctuationRate(maxFluctuationRateById.get(invId));
            ordered.add(inv);
        }
        inventoryService.updateBatchById(ordered);
        return ordered;
    }

    @GetMapping("/{inventoryId}")
    public GameRegionItem get(@PathVariable Integer inventoryId) {
        GameRegionItem inv = inventoryService.getById(inventoryId);
        if (inv == null) throw ApiException.notFound("库存记录不存在");
        return inv;
    }

    @PutMapping("/{inventoryId}")
    public GameRegionItem update(@PathVariable Integer inventoryId, @RequestBody GameRegionItem payload) {
        GameRegionItem inv = inventoryService.getById(inventoryId);
        if (inv == null) throw ApiException.notFound("库存记录不存在");
        if (payload.getStock() != null) { validateStock(payload.getStock()); inv.setStock(payload.getStock()); }
        if (payload.getPurchasePrice() != null) inv.setPurchasePrice(payload.getPurchasePrice());
        if (payload.getSellingPrice() != null) inv.setSellingPrice(payload.getSellingPrice());
        if (payload.getMinSellingPrice() != null) inv.setMinSellingPrice(payload.getMinSellingPrice());
        if (payload.getMaxSellingPrice() != null) inv.setMaxSellingPrice(payload.getMaxSellingPrice());
        if (payload.getMaxFluctuation() != null) inv.setMaxFluctuation(payload.getMaxFluctuation());
        if (payload.getMaxFluctuationRate() != null) inv.setMaxFluctuationRate(payload.getMaxFluctuationRate());
        inventoryService.updateById(inv);
        return inv;
    }

    private void validateStock(Integer stock) {
        if (stock == null) throw ApiException.badRequest("库存不能为空");
        if (stock < 0) throw ApiException.badRequest("库存不能为负数");
    }

    private Integer toInt(Object value) {
        if (value == null) return null;
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

    private BigDecimal toBigDecimal(Object value) {
        if (value == null) return null;
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
