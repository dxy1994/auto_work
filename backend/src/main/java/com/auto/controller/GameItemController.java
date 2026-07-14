package com.auto.controller;

import com.auto.common.ApiException;
import com.auto.common.PageRequests;
import com.auto.entity.GameItem;
import com.auto.entity.GameRegion;
import com.auto.entity.GameRegionItem;
import com.auto.service.GameItemService;
import com.auto.service.GameRegionItemService;
import com.auto.service.GameRegionService;
import com.baomidou.mybatisplus.core.metadata.IPage;
import org.springframework.http.HttpStatus;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;

import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/** 游戏物品管理。 */
@RestController
@RequestMapping("/api/game-items")
public class GameItemController {

    private final GameItemService itemService;
    private final GameRegionService regionService;
    private final GameRegionItemService inventoryService;

    public GameItemController(GameItemService itemService, GameRegionService regionService,
                              GameRegionItemService inventoryService) {
        this.itemService = itemService;
        this.regionService = regionService;
        this.inventoryService = inventoryService;
    }

    @GetMapping
    public Map<String, Object> list(
            @RequestParam(name = "game_id", required = false) Integer gameId,
            @RequestParam(name = "parent_id", required = false) Integer parentId,
            @RequestParam(name = "is_bundle", required = false) Integer isBundle,
            @RequestParam(name = "category", required = false) String category,
            @RequestParam(name = "keyword", required = false) String keyword,
            @RequestParam(name = "page", defaultValue = "1") int page,
            @RequestParam(name = "page_size", defaultValue = "20") int pageSize) {
        IPage<GameItem> result = itemService.search(gameId, parentId, isBundle, category, keyword,
                PageRequests.of(page, pageSize));
        return Map.of("total", result.getTotal(), "items", result.getRecords());
    }

    @GetMapping("/all")
    public List<GameItem> listAll(
            @RequestParam(name = "game_id", required = false) Integer gameId,
            @RequestParam(name = "is_bundle", required = false) Integer isBundle,
            @RequestParam(name = "no_parent", defaultValue = "false") boolean noParent) {
        return itemService.findAllActive(gameId, isBundle, noParent);
    }

    @GetMapping("/bundles")
    public List<GameItem> bundles(@RequestParam(name = "game_id", required = false) Integer gameId) {
        return itemService.findBundles(gameId);
    }

    @GetMapping("/bundle/{bundleId}/children")
    public List<GameItem> bundleChildren(@PathVariable Integer bundleId) {
        return itemService.findByParentIdActive(bundleId);
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
        itemService.save(payload);
        initItemInventory(payload);
        return payload;
    }

    /** 为新物品初始化该游戏下所有有效大区的库存记录（默认 0）。 */
    private void initItemInventory(GameItem item) {
        Set<Integer> existing = new HashSet<>();
        for (GameRegionItem inv : inventoryService.findByItemId(item.getId())) {
            existing.add(inv.getRegionId());
        }
        for (GameRegion region : regionService.findByGameIdActive(item.getGameId())) {
            if (existing.contains(region.getId())) continue;
            GameRegionItem inv = new GameRegionItem();
            inv.setGameId(item.getGameId());
            inv.setRegionId(region.getId());
            inv.setItemId(item.getId());
            inv.setStock(0);
            inventoryService.save(inv);
        }
    }

    @PutMapping("/{itemId}")
    public GameItem update(@PathVariable Integer itemId, @RequestBody GameItem payload) {
        GameItem item = itemService.getById(itemId);
        if (item == null) throw ApiException.notFound("物品不存在");
        if (payload.getParentId() != null) item.setParentId(payload.getParentId());
        if (payload.getName() != null) item.setName(payload.getName());
        if (payload.getCode() != null) item.setCode(payload.getCode());
        if (payload.getImage() != null) item.setImage(payload.getImage());
        if (payload.getIsBundle() != null) item.setIsBundle(payload.getIsBundle());
        if (payload.getCategory() != null) item.setCategory(payload.getCategory());
        if (payload.getPrice() != null) item.setPrice(payload.getPrice());
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
        item.setIsActive(0);
        itemService.updateById(item);
    }
}
