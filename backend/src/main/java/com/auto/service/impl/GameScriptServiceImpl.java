package com.auto.service.impl;

import com.auto.entity.GameScript;
import com.auto.mapper.GameScriptMapper;
import com.auto.service.GameScriptService;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.spring.service.impl.ServiceImpl;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class GameScriptServiceImpl extends ServiceImpl<GameScriptMapper, GameScript>
        implements GameScriptService {

    @Override
    public IPage<GameScript> search(Integer gameId, String category, String keyword, Page<GameScript> page) {
        LambdaQueryWrapper<GameScript> w = new LambdaQueryWrapper<>();
        w.eq(GameScript::getIsActive, 1)
                .eq(gameId != null, GameScript::getGameId, gameId)
                .eq(category != null, GameScript::getCategory, category)
                .like(keyword != null, GameScript::getTitle, keyword)
                .orderByAsc(GameScript::getSortOrder)
                .orderByDesc(GameScript::getId);
        return page(page, w);
    }

    @Override
    public List<GameScript> findAllActive(Integer gameId) {
        return list(new LambdaQueryWrapper<GameScript>()
                .eq(GameScript::getIsActive, 1)
                .eq(gameId != null, GameScript::getGameId, gameId)
                .orderByAsc(GameScript::getSortOrder));
    }
}
