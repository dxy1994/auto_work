package com.auto.service.impl;

import com.auto.entity.GameItem;
import com.auto.mapper.GameItemMapper;
import com.auto.service.ItemBundleRelationService;
import com.auto.service.GameItemService;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.spring.service.impl.ServiceImpl;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class GameItemServiceImpl extends ServiceImpl<GameItemMapper, GameItem> implements GameItemService {

    private final ItemBundleRelationService bundleItemService;

    public GameItemServiceImpl(ItemBundleRelationService bundleItemService) {
        this.bundleItemService = bundleItemService;
    }

    @Override
    public IPage<GameItem> search(Integer gameId, Integer isBundle,
                                  String category, String keyword, Integer excludeBundleId,
                                  Page<GameItem> page) {
        LambdaQueryWrapper<GameItem> w = new LambdaQueryWrapper<>();
        w.eq(GameItem::getIsActive, 1)
                .eq(gameId != null, GameItem::getGameId, gameId)
                .eq(isBundle != null, GameItem::getIsBundle, isBundle)
                .eq(category != null, GameItem::getCategory, category)
                .and(keyword != null, w2 -> w2
                        .like(GameItem::getName, keyword)
                        .or()
                        .like(GameItem::getCode, keyword));
        if (excludeBundleId != null) {
            List<Integer> excludedIds = bundleItemService.findItemIdsByBundleId(excludeBundleId);
            if (!excludedIds.isEmpty()) {
                w.notIn(GameItem::getId, excludedIds);
            }
        }
        w.orderByAsc(GameItem::getSortOrder)
         .orderByDesc(GameItem::getId);
        return page(page, w);
    }

    @Override
    public List<GameItem> findAllActive(Integer gameId, Integer isBundle) {
        LambdaQueryWrapper<GameItem> w = new LambdaQueryWrapper<>();
        w.eq(GameItem::getIsActive, 1)
                .eq(gameId != null, GameItem::getGameId, gameId)
                .eq(isBundle != null, GameItem::getIsBundle, isBundle)
                .orderByAsc(GameItem::getSortOrder);
        return list(w);
    }

    @Override
    public List<GameItem> findBundles(Integer gameId) {
        return list(new LambdaQueryWrapper<GameItem>()
                .eq(GameItem::getIsActive, 1)
                .eq(GameItem::getIsBundle, 1)
                .eq(gameId != null, GameItem::getGameId, gameId)
                .orderByAsc(GameItem::getSortOrder));
    }

    @Override
    public GameItem findByGameIdAndCode(Integer gameId, String code) {
        return getOne(new LambdaQueryWrapper<GameItem>()
                .eq(GameItem::getGameId, gameId)
                .eq(GameItem::getCode, code), false);
    }

    @Override
    public GameItem findByGameIdAndName(Integer gameId, String name) {
        return getOne(new LambdaQueryWrapper<GameItem>()
                .eq(GameItem::getGameId, gameId)
                .eq(GameItem::getName, name)
                .eq(GameItem::getIsActive, 1), false);
    }

    @Override
    public GameItem findActiveByGameIdAndCodeOrName(Integer gameId, String codeOrName) {
        GameItem matchedByCode = findByGameIdAndCode(gameId, codeOrName);
        if (matchedByCode != null && Integer.valueOf(1).equals(matchedByCode.getIsActive())) {
            return matchedByCode;
        }
        return findByGameIdAndName(gameId, codeOrName);
    }

    @Override
    public List<GameItem> findByGameIdActive(Integer gameId) {
        return list(new LambdaQueryWrapper<GameItem>()
                .eq(GameItem::getGameId, gameId)
                .eq(GameItem::getIsActive, 1));
    }

    @Override
    public int getNextSortOrder(Integer gameId, String category) {
        LambdaQueryWrapper<GameItem> w = new LambdaQueryWrapper<>();
        w.eq(GameItem::getGameId, gameId)
         .eq(category != null, GameItem::getCategory, category)
         .eq(GameItem::getIsActive, 1)
         .orderByDesc(GameItem::getSortOrder)
         .last("LIMIT 1");
        GameItem last = getOne(w, false);
        return last == null || last.getSortOrder() == null ? 1 : last.getSortOrder() + 1;
    }
}
