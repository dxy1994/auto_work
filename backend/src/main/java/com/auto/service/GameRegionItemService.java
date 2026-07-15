package com.auto.service;

import com.auto.entity.GameRegionItem;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.spring.service.IService;

import java.util.List;
import java.util.Map;

public interface GameRegionItemService extends IService<GameRegionItem> {

    IPage<Map<String, Object>> searchWithItem(Integer gameId, Integer regionId, Integer itemId,
                                              Integer hasStock, String keyword,
                                              Page<Map<String, Object>> page);

    List<Map<String, Object>> findAllWithItem(Integer gameId, Integer regionId);

    List<GameRegionItem> findByRegionId(Integer regionId);

    List<GameRegionItem> findByItemId(Integer itemId);
}
