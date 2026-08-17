package com.auto.service;

import com.auto.entity.GameAccount;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.spring.service.IService;

import java.util.List;

public interface GameAccountService extends IService<GameAccount> {

    IPage<GameAccount> search(Integer gameId, Integer regionId,
                              List<String> status, String keyword, Page<GameAccount> page);

    List<GameAccount> findIdleByGameAndRegion(Integer gameId, Integer regionId);

    /** 查找支持指定游戏和大区的全部启用账号，供忙碌机器排队选择使用。 */
    List<GameAccount> findActiveByGameAndRegion(Integer gameId, Integer regionId);
}
