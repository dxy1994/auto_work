package com.auto.service;

import com.auto.entity.GameItemOrderDetail;
import com.baomidou.mybatisplus.extension.service.IService;

import java.math.BigDecimal;
import java.util.List;

public interface GameItemOrderDetailService extends IService<GameItemOrderDetail> {

    List<GameItemOrderDetail> findByOrderIdOrderById(Integer orderId);

    List<GameItemOrderDetail> findByOrderId(Integer orderId);

    BigDecimal sumSubtotalByOrderId(Integer orderId);
}
