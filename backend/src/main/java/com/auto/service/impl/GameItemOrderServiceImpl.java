package com.auto.service.impl;

import com.auto.entity.GameItemOrder;
import com.auto.mapper.GameItemOrderMapper;
import com.auto.service.GameItemOrderService;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import org.springframework.stereotype.Service;

@Service
public class GameItemOrderServiceImpl extends ServiceImpl<GameItemOrderMapper, GameItemOrder>
        implements GameItemOrderService {

    @Override
    public IPage<GameItemOrder> search(Integer gameId, String status, String keyword, Page<GameItemOrder> page) {
        LambdaQueryWrapper<GameItemOrder> w = new LambdaQueryWrapper<>();
        w.eq(gameId != null, GameItemOrder::getGameId, gameId)
                .eq(status != null, GameItemOrder::getStatus, status)
                .and(keyword != null, q -> q.like(GameItemOrder::getOrderNo, keyword)
                        .or().like(GameItemOrder::getCustomerName, keyword))
                .orderByDesc(GameItemOrder::getId);
        return page(page, w);
    }
}
