package com.auto.controller;

import com.auto.common.ApiException;
import com.auto.common.PageRequests;
import com.auto.entity.Game;
import com.auto.service.GameService;
import com.baomidou.mybatisplus.core.metadata.IPage;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/** 游戏管理。 */
@RestController
@RequestMapping("/api/games")
public class GameController {

    private static final int DEFAULT_TRADE_TIMEOUT_SECONDS = 600;
    private static final int MIN_TRADE_TIMEOUT_SECONDS = 30;
    private static final int MAX_TRADE_TIMEOUT_SECONDS = 7200;

    private final GameService gameService;

    public GameController(GameService gameService) {
        this.gameService = gameService;
    }

    @GetMapping
    public Map<String, Object> list(
            @RequestParam(name = "page", defaultValue = "1") int page,
            @RequestParam(name = "page_size", defaultValue = "20") int pageSize,
            @RequestParam(name = "keyword", required = false) String keyword,
            @RequestParam(name = "platform", required = false) String platform) {
        IPage<Game> result = gameService.search(keyword, platform, PageRequests.of(page, pageSize));
        return Map.of("total", result.getTotal(), "items", result.getRecords());
    }

    @GetMapping("/all")
    public List<Game> listAll() {
        return gameService.findAllActiveOrdered();
    }

    @GetMapping("/{id}")
    public Game get(@PathVariable Integer id) {
        Game g = gameService.getById(id);
        if (g == null) throw ApiException.notFound("游戏不存在");
        return g;
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public Game create(@RequestBody Game payload) {
        if (gameService.findByCode(payload.getCode()) != null) {
            throw ApiException.badRequest("游戏编码 " + payload.getCode() + " 已存在");
        }
        payload.setId(null);
        payload.setIsActive(1);
        payload.setTradeTimeoutSeconds(validateTradeTimeout(payload.getTradeTimeoutSeconds()));
        gameService.save(payload);
        return payload;
    }

    @PutMapping("/{id}")
    public Game update(@PathVariable Integer id, @RequestBody Game payload) {
        Game g = gameService.getById(id);
        if (g == null) throw ApiException.notFound("游戏不存在");
        if (payload.getName() != null) g.setName(payload.getName());
        if (payload.getCode() != null) g.setCode(payload.getCode());
        if (payload.getIcon() != null) g.setIcon(payload.getIcon());
        if (payload.getPlatform() != null) g.setPlatform(payload.getPlatform());
        if (payload.getRemark() != null) g.setRemark(payload.getRemark());
        if (payload.getTradeType() != null) g.setTradeType(payload.getTradeType());
        if (payload.getTradeTimeoutSeconds() != null) {
            g.setTradeTimeoutSeconds(validateTradeTimeout(payload.getTradeTimeoutSeconds()));
        }
        if (payload.getSortOrder() != null) g.setSortOrder(payload.getSortOrder());
        if (payload.getIsActive() != null) g.setIsActive(payload.getIsActive());
        gameService.updateById(g);
        return g;
    }

    @DeleteMapping("/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void delete(@PathVariable Integer id) {
        Game g = gameService.getById(id);
        if (g == null) throw ApiException.notFound("游戏不存在");
        gameService.removeById(id);
    }

    private int validateTradeTimeout(Integer seconds) {
        int value = seconds != null ? seconds : DEFAULT_TRADE_TIMEOUT_SECONDS;
        if (value < MIN_TRADE_TIMEOUT_SECONDS || value > MAX_TRADE_TIMEOUT_SECONDS) {
            throw ApiException.badRequest("交易超时时间必须在 30 到 7200 秒之间");
        }
        return value;
    }
}
