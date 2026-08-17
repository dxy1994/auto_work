package com.auto.service;

import com.auto.entity.GameRegionInventory;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.spring.service.IService;

import java.util.List;
import java.util.Map;

public interface GameRegionInventoryService extends IService<GameRegionInventory> {

    IPage<Map<String, Object>> searchWithItem(Integer gameId, Integer regionId, Integer itemId,
                                              Integer hasStock, String keyword, Integer accountId,
                                              Page<Map<String, Object>> page);

    List<Map<String, Object>> findAllWithItem(Integer gameId, Integer regionId, Integer accountId);

    List<GameRegionInventory> findByRegionId(Integer regionId);

    List<GameRegionInventory> findByItemId(Integer itemId);

    GameRegionInventory findByRegionIdAndItemId(Integer regionId, Integer itemId);
}
