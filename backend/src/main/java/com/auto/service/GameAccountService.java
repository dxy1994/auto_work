package com.auto.service;

import com.auto.entity.GameAccount;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.IService;

public interface GameAccountService extends IService<GameAccount> {

    IPage<GameAccount> search(Integer gameId, Integer regionId, Integer machineId,
                              String status, String keyword, Page<GameAccount> page);
}
