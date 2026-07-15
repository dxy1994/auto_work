package com.auto.service;

import com.auto.entity.GameRegion;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.spring.service.IService;

import java.util.List;

public interface GameRegionService extends IService<GameRegion> {

    IPage<GameRegion> search(Integer gameId, Page<GameRegion> page);

    List<GameRegion> findAllActive(Integer gameId);

    GameRegion findByGameIdAndCode(Integer gameId, String code);

    Integer maxSortOrder(Integer gameId);

    List<GameRegion> findByGameIdActive(Integer gameId);
}
