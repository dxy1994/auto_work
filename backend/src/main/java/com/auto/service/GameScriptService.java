package com.auto.service;

import com.auto.entity.GameScript;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.spring.service.IService;

import java.util.List;

public interface GameScriptService extends IService<GameScript> {

    IPage<GameScript> search(Integer gameId, String category, String keyword, Page<GameScript> page);

    List<GameScript> findAllActive(Integer gameId);
}
