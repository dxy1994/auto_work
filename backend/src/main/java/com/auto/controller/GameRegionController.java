package com.auto.controller;

import com.auto.common.ApiException;
import com.auto.common.PageRequests;
import com.auto.entity.GameItem;
import com.auto.entity.GameRegion;
import com.auto.entity.GameRegionInventory;
import com.auto.service.GameItemService;
import com.auto.service.GameRegionInventoryService;
import com.auto.service.GameRegionInventoryShopPriceService;
import com.auto.service.GameRegionService;
import com.baomidou.mybatisplus.core.metadata.IPage;
import org.springframework.http.HttpStatus;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;

import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/** 游戏大区管理。 */
@RestController
@RequestMapping("/api/game-regions")
public class GameRegionController {

    private final GameRegionService regionService;
    private final GameItemService itemService;
    private final GameRegionInventoryService inventoryService;
    private final GameRegionInventoryShopPriceService shopPriceService;

    public GameRegionController(GameRegionService regionService, GameItemService itemService,
                                GameRegionInventoryService inventoryService,
                                GameRegionInventoryShopPriceService shopPriceService) {
        this.regionService = regionService;
        this.itemService = itemService;
        this.inventoryService = inventoryService;
        this.shopPriceService = shopPriceService;
    }

    @GetMapping
    public Map<String, Object> list(
            @RequestParam(name = "game_id", required = false) Integer gameId,
            @RequestParam(name = "page", defaultValue = "1") int page,
            @RequestParam(name = "page_size", defaultValue = "20") int pageSize) {
        IPage<GameRegion> result = regionService.search(gameId, PageRequests.of(page, pageSize));
        return Map.of("total", result.getTotal(), "items", result.getRecords());
    }

    @GetMapping("/all")
    public List<GameRegion> listAll(@RequestParam(name = "game_id", required = false) Integer gameId) {
        return regionService.findAllActive(gameId);
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    @Transactional
    public GameRegion create(@RequestBody GameRegion payload) {
        validateNavigation(payload);
        if (regionService.findByGameIdAndCode(payload.getGameId(), payload.getCode()) != null) {
            throw ApiException.badRequest("该游戏下大区编码 " + payload.getCode() + " 已存在");
        }
        Integer maxSort = regionService.maxSortOrder(payload.getGameId());
        int autoSort = (maxSort == null ? 0 : maxSort) + 1;
        payload.setId(null);
        if (payload.getSortOrder() == null) payload.setSortOrder(autoSort);
        if (payload.getSelectPage() == null) payload.setSelectPage(1);
        payload.setIsActive(1);
        regionService.save(payload);
        initRegionInventory(payload);
        return payload;
    }

    /** 为新大区初始化该游戏下所有有效物品的库存记录（默认 0）。 */
    private void initRegionInventory(GameRegion region) {
        Set<Integer> existing = new HashSet<>();
        for (GameRegionInventory inv : inventoryService.findByRegionId(region.getId())) {
            existing.add(inv.getItemId());
        }
        for (GameItem item : itemService.findByGameIdActive(region.getGameId())) {
            if (existing.contains(item.getId())) continue;
            GameRegionInventory inv = new GameRegionInventory();
            inv.setGameId(region.getGameId());
            inv.setRegionId(region.getId());
            inv.setItemId(item.getId());
            inv.setStock(0L);
            inventoryService.save(inv);
            shopPriceService.initForInventory(inv.getId());
        }
    }

    @PutMapping("/{regionId}")
    public GameRegion update(@PathVariable Integer regionId, @RequestBody GameRegion payload) {
        GameRegion r = regionService.getById(regionId);
        if (r == null) throw ApiException.notFound("大区不存在");
        validateNavigation(payload);
        if (payload.getName() != null) r.setName(payload.getName());
        if (payload.getCode() != null) r.setCode(payload.getCode());
        if (payload.getSortOrder() != null) r.setSortOrder(payload.getSortOrder());
        r.setSelectX(payload.getSelectX());
        r.setSelectY(payload.getSelectY());
        if (payload.getSelectPage() != null) r.setSelectPage(payload.getSelectPage());
        if (payload.getIsActive() != null) r.setIsActive(payload.getIsActive());
        regionService.updateById(r);
        return r;
    }

    @DeleteMapping("/{regionId}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void delete(@PathVariable Integer regionId) {
        GameRegion r = regionService.getById(regionId);
        if (r == null) throw ApiException.notFound("大区不存在");
        regionService.removeById(regionId);
    }

    private void validateNavigation(GameRegion payload) {
        if (payload.getSelectPage() != null && payload.getSelectPage() < 1) {
            throw ApiException.badRequest("大区页码必须大于或等于 1");
        }
        Integer x = payload.getSelectX();
        Integer y = payload.getSelectY();
        if (x == null && y == null) return;
        if (x == null || y == null) {
            throw ApiException.badRequest("大区选择坐标 X、Y 必须同时填写");
        }
        if (x < 0 || x >= 800 || y < 0 || y >= 600) {
            throw ApiException.badRequest("大区选择坐标必须位于 800x600 游戏客户区内");
        }
    }
}
