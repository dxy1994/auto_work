package com.auto.service.impl;

import com.auto.entity.GameAccount;
import com.auto.entity.GameAccountRegion;
import com.auto.mapper.GameAccountMapper;
import com.auto.service.GameAccountRegionService;
import com.auto.service.GameAccountService;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.spring.service.impl.ServiceImpl;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class GameAccountServiceImpl extends ServiceImpl<GameAccountMapper, GameAccount>
        implements GameAccountService {

    private final GameAccountRegionService gameAccountRegionService;

    public GameAccountServiceImpl(GameAccountRegionService gameAccountRegionService) {
        this.gameAccountRegionService = gameAccountRegionService;
    }

    @Override
    public IPage<GameAccount> search(Integer gameId, Integer regionId,
                                     List<String> status, String keyword, Page<GameAccount> page) {
        LambdaQueryWrapper<GameAccount> w = new LambdaQueryWrapper<>();
        w.eq(GameAccount::getIsActive, 1)
                .eq(gameId != null, GameAccount::getGameId, gameId)
                .in(status != null && !status.isEmpty(), GameAccount::getStatus, status)
                .and(keyword != null, q -> q.like(GameAccount::getAccountName, keyword)
                        .or().like(GameAccount::getNickname, keyword));

        // 如果指定大区，通过 game_account_regions 联表过滤
        if (regionId != null) {
            List<Integer> accountIds = gameAccountRegionService.findByRegionIdActive(regionId).stream()
                    .map(GameAccountRegion::getGameAccountId)
                    .distinct()
                    .toList();
            if (accountIds.isEmpty()) {
                w.eq(GameAccount::getId, -1); // 无匹配账号，返回空
            } else {
                w.in(GameAccount::getId, accountIds);
            }
        }

        w.orderByDesc(GameAccount::getId);
        return page(page, w);
    }

    @Override
    public List<GameAccount> findIdleByGameAndRegion(Integer gameId, Integer regionId) {
        // 通过 game_account_regions 联表查询：先找到该游戏+大区下的关联账号
        List<Integer> accountIds = gameAccountRegionService.findByGameIdAndRegionIdActive(gameId, regionId).stream()
                .map(GameAccountRegion::getGameAccountId)
                .distinct()
                .toList();
        if (accountIds.isEmpty()) return List.of();

        return list(new LambdaQueryWrapper<GameAccount>()
                .in(GameAccount::getId, accountIds)
                .eq(GameAccount::getStatus, "idle")
                .eq(GameAccount::getIsActive, 1)
                .orderByAsc(GameAccount::getId));
    }

    @Override
    public List<GameAccount> findActiveByGameAndRegion(Integer gameId, Integer regionId) {
        List<Integer> accountIds = gameAccountRegionService.findByGameIdAndRegionIdActive(gameId, regionId).stream()
                .map(GameAccountRegion::getGameAccountId)
                .distinct()
                .toList();
        if (accountIds.isEmpty()) return List.of();

        return list(new LambdaQueryWrapper<GameAccount>()
                .in(GameAccount::getId, accountIds)
                .eq(GameAccount::getIsActive, 1)
                .orderByAsc(GameAccount::getId));
    }
}
