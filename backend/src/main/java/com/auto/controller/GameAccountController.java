package com.auto.controller;

import com.auto.common.ApiException;
import com.auto.common.PageRequests;
import com.auto.entity.GameAccount;
import com.auto.service.CryptoService;
import com.auto.service.GameAccountService;
import com.baomidou.mybatisplus.core.metadata.IPage;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/** 游戏账号管理。 */
@RestController
@RequestMapping("/api/game-accounts")
public class GameAccountController {

    private final GameAccountService gameAccountService;
    private final CryptoService crypto;

    public GameAccountController(GameAccountService gameAccountService, CryptoService crypto) {
        this.gameAccountService = gameAccountService;
        this.crypto = crypto;
    }

    @GetMapping
    public Map<String, Object> list(
            @RequestParam(name = "game_id", required = false) Integer gameId,
            @RequestParam(name = "region_id", required = false) Integer regionId,
            @RequestParam(name = "machine_id", required = false) Integer machineId,
            @RequestParam(name = "status", required = false) List<String> status,
            @RequestParam(name = "keyword", required = false) String keyword,
            @RequestParam(name = "page", defaultValue = "1") int page,
            @RequestParam(name = "page_size", defaultValue = "20") int pageSize) {
        IPage<GameAccount> result = gameAccountService.search(gameId, regionId, machineId, status, keyword,
                PageRequests.of(page, pageSize));
        return Map.of("total", result.getTotal(), "items", result.getRecords());
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
        payload.setId(null);
        if (payload.getPassword() != null && !payload.getPassword().isEmpty()) {
            payload.setPassword(crypto.encrypt(payload.getPassword()));
        }
        payload.setIsActive(1);
        gameAccountService.save(payload);
        return payload;
    }

    @PutMapping("/{accountId}")
    public GameAccount update(@PathVariable Integer accountId, @RequestBody GameAccount payload) {
        GameAccount a = gameAccountService.getById(accountId);
        if (a == null) throw ApiException.notFound("游戏账号不存在");
        a.setRegionId(payload.getRegionId());
        if (payload.getMachineId() != null) a.setMachineId(payload.getMachineId());
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
        gameAccountService.updateById(a);
        return a;
    }

    @DeleteMapping("/{accountId}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void delete(@PathVariable Integer accountId) {
        GameAccount a = gameAccountService.getById(accountId);
        if (a == null) throw ApiException.notFound("游戏账号不存在");
        gameAccountService.removeById(accountId);
    }
}
