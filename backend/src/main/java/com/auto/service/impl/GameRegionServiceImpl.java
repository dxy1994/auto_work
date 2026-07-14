package com.auto.service.impl;

import com.auto.entity.GameRegion;
import com.auto.mapper.GameRegionMapper;
import com.auto.service.GameRegionService;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class GameRegionServiceImpl extends ServiceImpl<GameRegionMapper, GameRegion>
        implements GameRegionService {

    @Override
    public IPage<GameRegion> search(Integer gameId, Page<GameRegion> page) {
        LambdaQueryWrapper<GameRegion> w = new LambdaQueryWrapper<>();
        w.eq(GameRegion::getIsActive, 1)
                .eq(gameId != null, GameRegion::getGameId, gameId)
                .orderByAsc(GameRegion::getSortOrder)
                .orderByDesc(GameRegion::getId);
        return page(page, w);
    }

    @Override
    public List<GameRegion> findAllActive(Integer gameId) {
        return list(new LambdaQueryWrapper<GameRegion>()
                .eq(GameRegion::getIsActive, 1)
                .eq(gameId != null, GameRegion::getGameId, gameId)
                .orderByAsc(GameRegion::getSortOrder));
    }

    @Override
    public GameRegion findByGameIdAndCode(Integer gameId, String code) {
        return getOne(new LambdaQueryWrapper<GameRegion>()
                .eq(GameRegion::getGameId, gameId)
                .eq(GameRegion::getCode, code), false);
    }

    @Override
    public Integer maxSortOrder(Integer gameId) {
        return baseMapper.maxSortOrder(gameId);
    }

    @Override
    public List<GameRegion> findByGameIdActive(Integer gameId) {
        return list(new LambdaQueryWrapper<GameRegion>()
                .eq(GameRegion::getGameId, gameId)
                .eq(GameRegion::getIsActive, 1));
    }
}
