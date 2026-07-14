package com.auto.service.impl;

import com.auto.entity.GameAccount;
import com.auto.mapper.GameAccountMapper;
import com.auto.service.GameAccountService;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class GameAccountServiceImpl extends ServiceImpl<GameAccountMapper, GameAccount>
        implements GameAccountService {

    @Override
    public IPage<GameAccount> search(Integer gameId, Integer regionId, Integer machineId,
                                     String status, String keyword, Page<GameAccount> page) {
        LambdaQueryWrapper<GameAccount> w = new LambdaQueryWrapper<>();
        w.eq(GameAccount::getIsActive, 1)
                .eq(gameId != null, GameAccount::getGameId, gameId)
                .eq(regionId != null, GameAccount::getRegionId, regionId)
                .eq(machineId != null, GameAccount::getMachineId, machineId)
                .eq(status != null, GameAccount::getStatus, status)
                .and(keyword != null, q -> q.like(GameAccount::getAccountName, keyword)
                        .or().like(GameAccount::getNickname, keyword))
                .orderByDesc(GameAccount::getId);
        return page(page, w);
    }

    @Override
    public List<GameAccount> findIdleByGameAndRegion(Integer gameId, Integer regionId) {
        return list(new LambdaQueryWrapper<GameAccount>()
                .eq(GameAccount::getGameId, gameId)
                .eq(GameAccount::getRegionId, regionId)
                .eq(GameAccount::getStatus, "idle")
                .eq(GameAccount::getIsActive, 1)
                .isNotNull(GameAccount::getMachineId)
                .orderByAsc(GameAccount::getId));
    }
}
