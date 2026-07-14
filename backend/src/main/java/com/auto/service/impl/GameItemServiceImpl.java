package com.auto.service.impl;

import com.auto.entity.GameItem;
import com.auto.mapper.GameItemMapper;
import com.auto.service.GameItemService;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class GameItemServiceImpl extends ServiceImpl<GameItemMapper, GameItem> implements GameItemService {

    @Override
    public IPage<GameItem> search(Integer gameId, Integer parentId, Integer isBundle,
                                  String category, String keyword, Page<GameItem> page) {
        LambdaQueryWrapper<GameItem> w = new LambdaQueryWrapper<>();
        w.eq(GameItem::getIsActive, 1)
                .eq(gameId != null, GameItem::getGameId, gameId)
                .eq(parentId != null, GameItem::getParentId, parentId)
                .eq(isBundle != null, GameItem::getIsBundle, isBundle)
                .eq(category != null, GameItem::getCategory, category)
                .like(keyword != null, GameItem::getName, keyword)
                .orderByAsc(GameItem::getSortOrder)
                .orderByDesc(GameItem::getId);
        return page(page, w);
    }

    @Override
    public List<GameItem> findAllActive(Integer gameId, Integer isBundle, boolean noParent) {
        LambdaQueryWrapper<GameItem> w = new LambdaQueryWrapper<>();
        w.eq(GameItem::getIsActive, 1)
                .eq(gameId != null, GameItem::getGameId, gameId)
                .eq(isBundle != null, GameItem::getIsBundle, isBundle)
                .isNull(noParent, GameItem::getParentId)
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
    public List<GameItem> findByParentIdActive(Integer parentId) {
        return list(new LambdaQueryWrapper<GameItem>()
                .eq(GameItem::getParentId, parentId)
                .eq(GameItem::getIsActive, 1)
                .orderByAsc(GameItem::getSortOrder));
    }

    @Override
    public GameItem findByGameIdAndCode(Integer gameId, String code) {
        return getOne(new LambdaQueryWrapper<GameItem>()
                .eq(GameItem::getGameId, gameId)
                .eq(GameItem::getCode, code), false);
    }

    @Override
    public List<GameItem> findByGameIdActive(Integer gameId) {
        return list(new LambdaQueryWrapper<GameItem>()
                .eq(GameItem::getGameId, gameId)
                .eq(GameItem::getIsActive, 1));
    }
}
