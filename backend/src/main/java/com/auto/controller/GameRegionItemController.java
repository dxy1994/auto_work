package com.auto.controller;

import com.auto.common.ApiException;
import com.auto.common.PageRequests;
import com.auto.entity.GameRegionItem;
import com.auto.service.GameRegionItemService;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

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
            @RequestParam(name = "keyword", required = false) String keyword,
            @RequestParam(name = "page", defaultValue = "1") int page,
            @RequestParam(name = "page_size", defaultValue = "50") int pageSize) {
        Page<Map<String, Object>> pageObj = PageRequests.of(page, pageSize);
        IPage<Map<String, Object>> result = inventoryService.searchWithItem(gameId, regionId, keyword, pageObj);
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
        for (Object raw : items) {
            if (!(raw instanceof Map<?, ?> item)) {
                throw ApiException.badRequest("items 元素格式错误");
            }
            Integer id = toInt(item.get("id"));
            Integer stock = toInt(item.get("stock"));
            if (id == null) throw ApiException.badRequest("items 元素缺少 id");
            validateStock(stock);
            if (stockById.containsKey(id)) {
                throw ApiException.badRequest("items 中存在重复的 id: " + id);
            }
            stockById.put(id, stock);
        }
        List<Integer> ids = new ArrayList<>(stockById.keySet());
        List<GameRegionItem> existing = inventoryService.listByIds(ids);
        if (existing.size() != ids.size()) {
            throw ApiException.notFound("部分库存记录不存在");
        }
        List<GameRegionItem> ordered = new ArrayList<>();
        for (GameRegionItem inv : existing) {
            inv.setStock(stockById.get(inv.getId()));
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
        validateStock(payload.getStock());
        inv.setStock(payload.getStock());
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
}
