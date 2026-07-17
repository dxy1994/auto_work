package com.auto.controller;

import com.auto.common.ApiException;
import com.auto.common.PageRequests;
import com.auto.entity.GameScript;
import com.auto.entity.RegionScript;
import com.auto.service.GameScriptService;
import com.auto.service.RegionScriptService;
import com.baomidou.mybatisplus.core.metadata.IPage;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/** 话术管理（游戏话术 + 大区话术）。 */
@RestController
@RequestMapping("/api/scripts")
public class ScriptController {

    private final GameScriptService gameScriptService;
    private final RegionScriptService regionScriptService;

    public ScriptController(GameScriptService gameScriptService, RegionScriptService regionScriptService) {
        this.gameScriptService = gameScriptService;
        this.regionScriptService = regionScriptService;
    }

    // ── 游戏话术 ────────────────────────────────────────────────

    @GetMapping("/game")
    public Map<String, Object> listGameScripts(
            @RequestParam(name = "game_id", required = false) Integer gameId,
            @RequestParam(name = "category", required = false) String category,
            @RequestParam(name = "keyword", required = false) String keyword,
            @RequestParam(name = "page", defaultValue = "1") int page,
            @RequestParam(name = "page_size", defaultValue = "20") int pageSize) {
        IPage<GameScript> result = gameScriptService.search(gameId, category, keyword,
                PageRequests.of(page, pageSize));
        return Map.of("total", result.getTotal(), "items", result.getRecords());
    }

    @GetMapping("/game/all")
    public List<GameScript> listAllGameScripts(@RequestParam(name = "game_id", required = false) Integer gameId) {
        return gameScriptService.findAllActive(gameId);
    }

    @PostMapping("/game")
    @ResponseStatus(HttpStatus.CREATED)
    public GameScript createGameScript(@RequestBody GameScript payload) {
        payload.setId(null);
        payload.setIsActive(1);
        if (payload.getSortOrder() == null || payload.getSortOrder() == 0) {
            Integer maxSort = gameScriptService.maxSortOrder(payload.getGameId(), payload.getCategory());
            payload.setSortOrder((maxSort == null ? 0 : maxSort) + 1);
        }
        gameScriptService.save(payload);
        return payload;
    }

    @PutMapping("/game/{scriptId}")
    public GameScript updateGameScript(@PathVariable Integer scriptId, @RequestBody GameScript payload) {
        GameScript s = gameScriptService.getById(scriptId);
        if (s == null) throw ApiException.notFound("话术不存在");
        if (payload.getTitle() != null) s.setTitle(payload.getTitle());
        if (payload.getContent() != null) s.setContent(payload.getContent());
        if (payload.getImageUrl() != null) s.setImageUrl(payload.getImageUrl());
        if (payload.getCategory() != null) s.setCategory(payload.getCategory());
        if (payload.getSortOrder() != null) s.setSortOrder(payload.getSortOrder());
        if (payload.getIsActive() != null) s.setIsActive(payload.getIsActive());
        gameScriptService.updateById(s);
        return s;
    }

    @DeleteMapping("/game/{scriptId}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void deleteGameScript(@PathVariable Integer scriptId) {
        GameScript s = gameScriptService.getById(scriptId);
        if (s == null) throw ApiException.notFound("话术不存在");
        gameScriptService.removeById(scriptId);
    }

    // ── 大区话术 ────────────────────────────────────────────────

    @GetMapping("/region")
    public Map<String, Object> listRegionScripts(
            @RequestParam(name = "region_id", required = false) Integer regionId,
            @RequestParam(name = "category", required = false) String category,
            @RequestParam(name = "keyword", required = false) String keyword,
            @RequestParam(name = "page", defaultValue = "1") int page,
            @RequestParam(name = "page_size", defaultValue = "20") int pageSize) {
        IPage<RegionScript> result = regionScriptService.search(regionId, category, keyword,
                PageRequests.of(page, pageSize));
        return Map.of("total", result.getTotal(), "items", result.getRecords());
    }

    @PostMapping("/region")
    @ResponseStatus(HttpStatus.CREATED)
    public RegionScript createRegionScript(@RequestBody RegionScript payload) {
        payload.setId(null);
        payload.setIsActive(1);
        if (payload.getSortOrder() == null || payload.getSortOrder() == 0) {
            Integer maxSort = regionScriptService.maxSortOrder(payload.getRegionId(), payload.getCategory());
            payload.setSortOrder((maxSort == null ? 0 : maxSort) + 1);
        }
        regionScriptService.save(payload);
        return payload;
    }

    @PutMapping("/region/{scriptId}")
    public RegionScript updateRegionScript(@PathVariable Integer scriptId, @RequestBody RegionScript payload) {
        RegionScript s = regionScriptService.getById(scriptId);
        if (s == null) throw ApiException.notFound("话术不存在");
        if (payload.getGameScriptId() != null) s.setGameScriptId(payload.getGameScriptId());
        if (payload.getTitle() != null) s.setTitle(payload.getTitle());
        if (payload.getContent() != null) s.setContent(payload.getContent());
        if (payload.getImageUrl() != null) s.setImageUrl(payload.getImageUrl());
        if (payload.getCategory() != null) s.setCategory(payload.getCategory());
        if (payload.getSortOrder() != null) s.setSortOrder(payload.getSortOrder());
        if (payload.getIsActive() != null) s.setIsActive(payload.getIsActive());
        regionScriptService.updateById(s);
        return s;
    }

    @DeleteMapping("/region/{scriptId}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void deleteRegionScript(@PathVariable Integer scriptId) {
        RegionScript s = regionScriptService.getById(scriptId);
        if (s == null) throw ApiException.notFound("话术不存在");
        regionScriptService.removeById(scriptId);
    }
}
