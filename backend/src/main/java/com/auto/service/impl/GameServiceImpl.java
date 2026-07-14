package com.auto.service.impl;

import com.auto.entity.Game;
import com.auto.mapper.GameMapper;
import com.auto.service.GameService;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class GameServiceImpl extends ServiceImpl<GameMapper, Game> implements GameService {

    @Override
    public IPage<Game> search(String keyword, String platform, Page<Game> page) {
        LambdaQueryWrapper<Game> w = new LambdaQueryWrapper<>();
        w.eq(Game::getIsActive, 1)
                .like(keyword != null, Game::getName, keyword)
                .eq(platform != null, Game::getPlatform, platform)
                .orderByAsc(Game::getSortOrder)
                .orderByDesc(Game::getId);
        return page(page, w);
    }

    @Override
    public List<Game> findAllActiveOrdered() {
        return list(new LambdaQueryWrapper<Game>()
                .eq(Game::getIsActive, 1)
                .orderByAsc(Game::getSortOrder));
    }

    @Override
    public Game findByCode(String code) {
        return getOne(new LambdaQueryWrapper<Game>().eq(Game::getCode, code), false);
    }
}
