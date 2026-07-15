package com.auto.service;

import com.auto.entity.GameItem;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.spring.service.IService;

import java.util.List;

public interface GameItemService extends IService<GameItem> {

    IPage<GameItem> search(Integer gameId, Integer parentId, Integer isBundle,
                           String category, String keyword, Page<GameItem> page);

    List<GameItem> findAllActive(Integer gameId, Integer isBundle, boolean noParent);

    List<GameItem> findBundles(Integer gameId);

    List<GameItem> findByParentIdActive(Integer parentId);

    GameItem findByGameIdAndCode(Integer gameId, String code);

    List<GameItem> findByGameIdActive(Integer gameId);
}
