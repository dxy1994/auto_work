package com.auto.service;

import com.auto.entity.GameItem;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.spring.service.IService;

import java.util.List;

public interface GameItemService extends IService<GameItem> {

    IPage<GameItem> search(Integer gameId, Integer isBundle,
                           String category, String keyword, Integer excludeBundleId,
                           Page<GameItem> page);

    List<GameItem> findAllActive(Integer gameId, Integer isBundle);

    List<GameItem> findBundles(Integer gameId);

    GameItem findByGameIdAndCode(Integer gameId, String code);

    /** 按游戏+物品名称精确匹配（启用中） */
    GameItem findByGameIdAndName(Integer gameId, String name);

    List<GameItem> findByGameIdActive(Integer gameId);

    /** 获取同一游戏+分类下的下一个排序号（自动递增） */
    int getNextSortOrder(Integer gameId, String category);
}
