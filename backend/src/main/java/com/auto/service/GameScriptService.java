package com.auto.service;

import com.auto.entity.GameScript;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.spring.service.IService;

import java.util.List;

public interface GameScriptService extends IService<GameScript> {

    IPage<GameScript> search(Integer gameId, String category, String keyword, Page<GameScript> page);

    List<GameScript> findAllActive(Integer gameId);

    /** 按游戏ID和分类获取第一条激活话术（按 sort_order 排序）。 */
    GameScript findFirstByGameIdAndCategory(int gameId, String category);

    /** 按游戏ID和分类获取全部激活话术（按 sort_order 排序）。 */
    List<GameScript> findAllByGameIdAndCategory(int gameId, String category);
}
