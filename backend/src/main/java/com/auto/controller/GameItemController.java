package com.auto.controller;

import com.auto.common.ApiException;
import com.auto.common.PageRequests;
import com.auto.entity.BundleChildVO;
import com.auto.entity.GameItem;
import com.auto.entity.ItemBundleRelation;
import com.auto.entity.GameRegion;
import com.auto.entity.GameRegionInventory;
import com.auto.service.ItemBundleRelationService;
import com.auto.service.GameItemService;
import com.auto.service.GameRegionInventoryService;
import com.auto.service.GameRegionInventoryShopPriceService;
import com.auto.service.GameRegionService;
import com.baomidou.mybatisplus.core.metadata.IPage;
import org.springframework.http.HttpStatus;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;

import java.util.*;
import java.util.stream.Collectors;

/** 游戏物品管理。 */
@RestController
@RequestMapping("/api/game-items")
public class GameItemController {

    private final GameItemService itemService;
    private final ItemBundleRelationService bundleItemService;
    private final GameRegionService regionService;
    private final GameRegionInventoryService inventoryService;
    private final GameRegionInventoryShopPriceService shopPriceService;

    public GameItemController(GameItemService itemService, ItemBundleRelationService bundleItemService,
                              GameRegionService regionService, GameRegionInventoryService inventoryService,
                              GameRegionInventoryShopPriceService shopPriceService) {
        this.itemService = itemService;
        this.bundleItemService = bundleItemService;
        this.regionService = regionService;
        this.inventoryService = inventoryService;
        this.shopPriceService = shopPriceService;
    }

    @GetMapping
    public Map<String, Object> list(
            @RequestParam(name = "game_id", required = false) Integer gameId,
            @RequestParam(name = "is_bundle", required = false) Integer isBundle,
            @RequestParam(name = "category", required = false) String category,
            @RequestParam(name = "keyword", required = false) String keyword,
            @RequestParam(name = "exclude_bundle_id", required = false) Integer excludeBundleId,
            @RequestParam(name = "page", defaultValue = "1") int page,
            @RequestParam(name = "page_size", defaultValue = "20") int pageSize) {
        IPage<GameItem> result = itemService.search(gameId, isBundle, category, keyword, excludeBundleId,
                PageRequests.of(page, pageSize));
        return Map.of("total", result.getTotal(), "items", result.getRecords());
    }

    @GetMapping("/all")
    public List<GameItem> listAll(
            @RequestParam(name = "game_id", required = false) Integer gameId,
            @RequestParam(name = "is_bundle", required = false) Integer isBundle,
            @RequestParam(name = "exclude_bundle_id", required = false) Integer excludeBundleId) {
        List<GameItem> items = itemService.findAllActive(gameId, isBundle);
        if (excludeBundleId != null) {
            Set<Integer> existingIds = new HashSet<>(bundleItemService.findItemIdsByBundleId(excludeBundleId));
            items = items.stream().filter(i -> !existingIds.contains(i.getId())).collect(Collectors.toList());
        }
        return items;
    }

    @GetMapping("/bundles")
    public List<GameItem> bundles(@RequestParam(name = "game_id", required = false) Integer gameId) {
        return itemService.findBundles(gameId);
    }

    /** 获取套装下的子物品列表（含数量） */
    @GetMapping("/bundle/{bundleId}/children")
    public List<BundleChildVO> bundleChildren(@PathVariable Integer bundleId) {
        List<ItemBundleRelation> relations = bundleItemService.findRelationsByBundleId(bundleId);
        if (relations.isEmpty()) return Collections.emptyList();
        List<Integer> itemIds = relations.stream().map(ItemBundleRelation::getItemId).collect(Collectors.toList());
        Map<Integer, GameItem> itemMap = itemService.listByIds(itemIds).stream()
                .filter(i -> i.getIsActive() == 1)
                .collect(Collectors.toMap(GameItem::getId, i -> i));
        return relations.stream()
                .filter(r -> itemMap.containsKey(r.getItemId()))
                .map(r -> BundleChildVO.from(itemMap.get(r.getItemId()), r.getQuantity()))
                .collect(Collectors.toList());
    }

    /** 批量添加物品到套装（支持指定数量） */
    @PostMapping("/bundle/{bundleId}/children")
    @Transactional
    public void addBundleChildren(@PathVariable Integer bundleId, @RequestBody Map<String, Object> payload) {
        // 支持新格式：{"items": [{"item_id": 1, "quantity": 2}]} 或旧格式：{"item_ids": [1, 2]}
        @SuppressWarnings("unchecked")
        List<Map<String, Object>> items = (List<Map<String, Object>>) payload.get("items");
        if (items != null) {
            // 新格式：逐条指定数量
            Map<Integer, Integer> itemQuantities = new LinkedHashMap<>();
            for (Map<String, Object> item : items) {
                Integer itemId = toInt(item.get("item_id"));
                Integer quantity = toInt(item.get("quantity"));
                if (itemId == null) continue;
                itemQuantities.put(itemId, quantity != null && quantity > 0 ? quantity : 1);
            }
            if (itemQuantities.isEmpty()) throw ApiException.badRequest("items 不能为空");
            bundleItemService.addItemsWithQuantity(bundleId, itemQuantities);
        } else {
            // 旧格式：仅 item_ids 列表（向后兼容）
            @SuppressWarnings("unchecked")
            List<Integer> itemIds = (List<Integer>) payload.get("item_ids");
            if (itemIds == null || itemIds.isEmpty()) throw ApiException.badRequest("item_ids 或 items 不能为空");
            bundleItemService.addItems(bundleId, itemIds);
        }
    }

    /** 从套装中移除物品 */
    @DeleteMapping("/bundle/{bundleId}/children/{itemId}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void removeBundleChild(@PathVariable Integer bundleId, @PathVariable Integer itemId) {
        bundleItemService.removeItem(bundleId, itemId);
    }

    @GetMapping("/{itemId}")
    public GameItem get(@PathVariable Integer itemId) {
        GameItem item = itemService.getById(itemId);
        if (item == null) throw ApiException.notFound("物品不存在");
        return item;
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    @Transactional
    public GameItem create(@RequestBody GameItem payload) {
        if (itemService.findByGameIdAndCode(payload.getGameId(), payload.getCode()) != null) {
            throw ApiException.badRequest("该游戏下物品编码 " + payload.getCode() + " 已存在");
        }
        payload.setId(null);
        payload.setIsActive(1);
        // 排序自动递增：同一游戏+分类下取最大值+1
        if (payload.getSortOrder() == null || payload.getSortOrder() == 0) {
            payload.setSortOrder(itemService.getNextSortOrder(payload.getGameId(), payload.getCategory()));
        }
        itemService.save(payload);
        initItemInventory(payload);
        return payload;
    }

    /** 为新物品初始化该游戏下所有有效大区的库存记录（默认 0）。 */
    private void initItemInventory(GameItem item) {
        Set<Integer> existing = new HashSet<>();
        for (GameRegionInventory inv : inventoryService.findByItemId(item.getId())) {
            existing.add(inv.getRegionId());
        }
        for (GameRegion region : regionService.findByGameIdActive(item.getGameId())) {
            if (existing.contains(region.getId())) continue;
            GameRegionInventory inv = new GameRegionInventory();
            inv.setGameId(item.getGameId());
            inv.setRegionId(region.getId());
            inv.setItemId(item.getId());
            inv.setStock(0L);
            inventoryService.save(inv);
            shopPriceService.initForInventory(inv.getId());
        }
    }

    @PutMapping("/{itemId}")
    public GameItem update(@PathVariable Integer itemId, @RequestBody GameItem payload) {
        GameItem item = itemService.getById(itemId);
        if (item == null) throw ApiException.notFound("物品不存在");
        if (payload.getName() != null) item.setName(payload.getName());
        if (payload.getCode() != null) item.setCode(payload.getCode());
        if (payload.getImage() != null) item.setImage(payload.getImage());
        if (payload.getSelectedImage() != null) item.setSelectedImage(payload.getSelectedImage());
        if (payload.getIsBundle() != null) item.setIsBundle(payload.getIsBundle());
        if (payload.getCategory() != null) item.setCategory(payload.getCategory());
        if (payload.getPrice() != null) item.setPrice(payload.getPrice());
        if (payload.getPosition() != null) item.setPosition(payload.getPosition());
        if (payload.getRemark() != null) item.setRemark(payload.getRemark());
        if (payload.getSortOrder() != null) item.setSortOrder(payload.getSortOrder());
        if (payload.getIsActive() != null) item.setIsActive(payload.getIsActive());
        itemService.updateById(item);
        return item;
    }

    @DeleteMapping("/{itemId}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void delete(@PathVariable Integer itemId) {
        GameItem item = itemService.getById(itemId);
        if (item == null) throw ApiException.notFound("物品不存在");
        itemService.removeById(itemId);
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
                return null;
            }
        }
        return null;
    }
}
