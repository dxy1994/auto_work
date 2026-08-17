package com.auto.service.impl;

import com.auto.entity.GameAccountRegion;
import com.auto.mapper.GameAccountRegionMapper;
import com.auto.service.GameAccountRegionService;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.spring.service.impl.ServiceImpl;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class GameAccountRegionServiceImpl extends ServiceImpl<GameAccountRegionMapper, GameAccountRegion>
        implements GameAccountRegionService {

    @Override
    public List<GameAccountRegion> findByAccountIdActive(Integer gameAccountId) {
        return list(new LambdaQueryWrapper<GameAccountRegion>()
                .eq(GameAccountRegion::getGameAccountId, gameAccountId)
                .eq(GameAccountRegion::getIsActive, 1));
    }

    @Override
    public List<GameAccountRegion> findByRegionIdActive(Integer regionId) {
        return list(new LambdaQueryWrapper<GameAccountRegion>()
                .eq(GameAccountRegion::getRegionId, regionId)
                .eq(GameAccountRegion::getIsActive, 1));
    }

    @Override
    public List<GameAccountRegion> findByGameIdAndRegionIdActive(Integer gameId, Integer regionId) {
        // 通过 mapper XML 联表查询 game_accounts 过滤 game_id
        return baseMapper.findByGameIdAndRegionIdActive(gameId, regionId);
    }

    @Override
    public List<Integer> findRegionIdsByAccountId(Integer gameAccountId) {
        return findByAccountIdActive(gameAccountId).stream()
                .map(GameAccountRegion::getRegionId)
                .toList();
    }
}
