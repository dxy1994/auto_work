package com.auto.service.impl;

import com.auto.entity.GameRegionInventory;
import com.auto.mapper.GameRegionInventoryMapper;
import com.auto.service.GameRegionInventoryService;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.spring.service.impl.ServiceImpl;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;

@Service
public class GameRegionInventoryServiceImpl extends ServiceImpl<GameRegionInventoryMapper, GameRegionInventory>
        implements GameRegionInventoryService {

    @Override
    public IPage<Map<String, Object>> searchWithItem(Integer gameId, Integer regionId, Integer itemId,
                                                     Integer hasStock, String keyword, Integer accountId,
                                                     Page<Map<String, Object>> page) {
        return baseMapper.searchWithItem(page, gameId, regionId, itemId, hasStock, keyword, accountId);
    }

    @Override
    public List<Map<String, Object>> findAllWithItem(Integer gameId, Integer regionId, Integer accountId) {
        return baseMapper.findAllWithItem(gameId, regionId, accountId);
    }

    @Override
    public List<GameRegionInventory> findByRegionId(Integer regionId) {
        return list(new LambdaQueryWrapper<GameRegionInventory>().eq(GameRegionInventory::getRegionId, regionId));
    }

    @Override
    public List<GameRegionInventory> findByItemId(Integer itemId) {
        return list(new LambdaQueryWrapper<GameRegionInventory>().eq(GameRegionInventory::getItemId, itemId));
    }

    @Override
    public GameRegionInventory findByRegionIdAndItemId(Integer regionId, Integer itemId) {
        return getOne(new LambdaQueryWrapper<GameRegionInventory>()
                .eq(GameRegionInventory::getRegionId, regionId)
                .eq(GameRegionInventory::getItemId, itemId)
                .eq(GameRegionInventory::getIsActive, 1), false);
    }
}
