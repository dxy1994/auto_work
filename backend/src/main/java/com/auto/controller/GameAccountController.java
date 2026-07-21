package com.auto.controller;

import com.auto.common.ApiException;
import com.auto.common.PageRequests;
import com.auto.entity.GameAccount;
import com.auto.entity.GameAccountRegion;
import com.auto.service.CryptoService;
import com.auto.service.GameAccountRegionService;
import com.auto.service.GameAccountService;
import com.baomidou.mybatisplus.core.metadata.IPage;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/** 游戏账号管理。 */
@RestController
@RequestMapping("/api/game-accounts")
public class GameAccountController {

    private final GameAccountService gameAccountService;
    private final GameAccountRegionService gameAccountRegionService;
    private final CryptoService crypto;

    public GameAccountController(GameAccountService gameAccountService,
                                 GameAccountRegionService gameAccountRegionService,
                                 CryptoService crypto) {
        this.gameAccountService = gameAccountService;
        this.gameAccountRegionService = gameAccountRegionService;
        this.crypto = crypto;
    }

    @GetMapping
    public Map<String, Object> list(
            @RequestParam(name = "game_id", required = false) Integer gameId,
            @RequestParam(name = "region_id", required = false) Integer regionId,
            @RequestParam(name = "status", required = false) List<String> status,
            @RequestParam(name = "keyword", required = false) String keyword,
            @RequestParam(name = "page", defaultValue = "1") int page,
            @RequestParam(name = "page_size", defaultValue = "20") int pageSize) {
        IPage<GameAccount> result = gameAccountService.search(gameId, regionId, status, keyword,
                PageRequests.of(page, pageSize));
        // 为每个账号附加 region_ids
        List<Map<String, Object>> items = new ArrayList<>();
        for (GameAccount a : result.getRecords()) {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("id", a.getId());
            item.put("game_id", a.getGameId());
            item.put("region_ids", gameAccountRegionService.findRegionIdsByAccountId(a.getId()));
            item.put("account_name", a.getAccountName());
            item.put("account_no", a.getAccountNo());
            item.put("nickname", a.getNickname());
            item.put("level", a.getLevel());
            item.put("status", a.getStatus());
            item.put("is_active", a.getIsActive());
            item.put("extra_fields", a.getExtraFields());
            item.put("created_at", a.getCreatedAt());
            item.put("updated_at", a.getUpdatedAt());
            items.add(item);
        }
        return Map.of("total", result.getTotal(), "items", items);
    }

    @GetMapping("/{accountId}")
    public GameAccount get(@PathVariable Integer accountId) {
        GameAccount a = gameAccountService.getById(accountId);
        if (a == null) throw ApiException.notFound("游戏账号不存在");
        return a;
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public GameAccount create(@RequestBody GameAccount payload) {
        requireRegions(payload.getRegionIds());
        payload.setId(null);
        if (payload.getPassword() != null && !payload.getPassword().isEmpty()) {
            payload.setPassword(crypto.encrypt(payload.getPassword()));
        }
        payload.setIsActive(1);
        gameAccountService.save(payload);

        // 保存大区关联
        syncAccountRegions(payload.getId(), payload.getRegionIds());
        return payload;
    }

    @PutMapping("/{accountId}")
    public GameAccount update(@PathVariable Integer accountId, @RequestBody GameAccount payload) {
        GameAccount a = gameAccountService.getById(accountId);
        if (a == null) throw ApiException.notFound("游戏账号不存在");
        if (payload.getAccountName() != null) a.setAccountName(payload.getAccountName());
        if (payload.getAccountNo() != null) a.setAccountNo(payload.getAccountNo());
        if (payload.getPassword() != null && !payload.getPassword().isEmpty()) {
            a.setPassword(crypto.encrypt(payload.getPassword()));
        }
        if (payload.getNickname() != null) a.setNickname(payload.getNickname());
        if (payload.getLevel() != null) a.setLevel(payload.getLevel());
        if (payload.getExtraFields() != null) a.setExtraFields(payload.getExtraFields());
        if (payload.getStatus() != null) a.setStatus(payload.getStatus());
        if (payload.getIsActive() != null) a.setIsActive(payload.getIsActive());
        if (payload.getRegionIds() != null) {
            requireRegions(payload.getRegionIds());
        }
        gameAccountService.updateById(a);

        // 同步大区关联
        if (payload.getRegionIds() != null) {
            syncAccountRegions(accountId, payload.getRegionIds());
        }
        return a;
    }

    @DeleteMapping("/{accountId}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void delete(@PathVariable Integer accountId) {
        GameAccount a = gameAccountService.getById(accountId);
        if (a == null) throw ApiException.notFound("游戏账号不存在");
        gameAccountService.removeById(accountId);
    }

    // ── 辅助方法 ────────────────────────────────────────────

    /** 同步账号的大区关联：全量替换为传入的 regionIds 列表。 */
    private void syncAccountRegions(Integer accountId, List<Integer> regionIds) {
        if (regionIds == null) return;
        // 删除旧关联
        List<GameAccountRegion> existing = gameAccountRegionService.findByAccountIdActive(accountId);
        for (GameAccountRegion gar : existing) {
            gameAccountRegionService.removeById(gar.getId());
        }
        // 插入新关联
        for (Integer regionId : regionIds.stream().distinct().toList()) {
            GameAccountRegion gar = new GameAccountRegion();
            gar.setGameAccountId(accountId);
            gar.setRegionId(regionId);
            gar.setIsActive(1);
            gameAccountRegionService.save(gar);
        }
    }

    private void requireRegions(List<Integer> regionIds) {
        if (regionIds == null || regionIds.isEmpty() || regionIds.stream().anyMatch(id -> id == null)) {
            throw ApiException.badRequest("游戏账号至少需要关联一个大区");
        }
    }
}
