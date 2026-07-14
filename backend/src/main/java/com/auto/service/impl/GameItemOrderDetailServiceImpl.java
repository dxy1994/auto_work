package com.auto.service.impl;

import com.auto.entity.GameItemOrderDetail;
import com.auto.mapper.GameItemOrderDetailMapper;
import com.auto.service.GameItemOrderDetailService;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.util.List;

@Service
public class GameItemOrderDetailServiceImpl
        extends ServiceImpl<GameItemOrderDetailMapper, GameItemOrderDetail>
        implements GameItemOrderDetailService {

    @Override
    public List<GameItemOrderDetail> findByOrderIdOrderById(Integer orderId) {
        return list(new LambdaQueryWrapper<GameItemOrderDetail>()
                .eq(GameItemOrderDetail::getOrderId, orderId)
                .orderByAsc(GameItemOrderDetail::getId));
    }

    @Override
    public List<GameItemOrderDetail> findByOrderId(Integer orderId) {
        return list(new LambdaQueryWrapper<GameItemOrderDetail>()
                .eq(GameItemOrderDetail::getOrderId, orderId));
    }

    @Override
    public BigDecimal sumSubtotalByOrderId(Integer orderId) {
        return baseMapper.sumSubtotalByOrderId(orderId);
    }
}
