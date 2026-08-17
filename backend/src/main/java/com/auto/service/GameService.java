package com.auto.service;

import com.auto.entity.Game;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.spring.service.IService;

import java.util.List;

public interface GameService extends IService<Game> {

    IPage<Game> search(String keyword, String platform, Page<Game> page);

    List<Game> findAllActiveOrdered();

    Game findByCode(String code);

    Game findByName(String name);
}
