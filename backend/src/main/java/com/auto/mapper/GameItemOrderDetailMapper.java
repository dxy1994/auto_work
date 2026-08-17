package com.auto.mapper;

import com.auto.entity.GameItemOrderDetail;
import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.math.BigDecimal;

@Mapper
public interface GameItemOrderDetailMapper extends BaseMapper<GameItemOrderDetail> {

    BigDecimal sumSubtotalByOrderId(@Param("orderId") Integer orderId);
}
