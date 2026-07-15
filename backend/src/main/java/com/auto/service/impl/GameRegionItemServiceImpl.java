package com.auto.service.impl;

import com.auto.entity.GameRegionItem;
import com.auto.mapper.GameRegionItemMapper;
import com.auto.service.GameRegionItemService;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.spring.service.impl.ServiceImpl;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;

@Service
public class GameRegionItemServiceImpl extends ServiceImpl<GameRegionItemMapper, GameRegionItem>
        implements GameRegionItemService {

    @Override
    public IPage<Map<String, Object>> searchWithItem(Integer gameId, Integer regionId, Integer itemId,
                                                     Integer hasStock, String keyword,
                                                     Page<Map<String, Object>> page) {
        return baseMapper.searchWithItem(page, gameId, regionId, itemId, hasStock, keyword);
    }

    @Override
    public List<Map<String, Object>> findAllWithItem(Integer gameId, Integer regionId) {
        return baseMapper.findAllWithItem(gameId, regionId);
    }

    @Override
    public List<GameRegionItem> findByRegionId(Integer regionId) {
        return list(new LambdaQueryWrapper<GameRegionItem>().eq(GameRegionItem::getRegionId, regionId));
    }

    @Override
    public List<GameRegionItem> findByItemId(Integer itemId) {
        return list(new LambdaQueryWrapper<GameRegionItem>().eq(GameRegionItem::getItemId, itemId));
    }
}
