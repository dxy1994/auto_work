package com.auto.mapper;

import com.auto.entity.GameItemOrderDetail;
import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.math.BigDecimal;

@Mapper
public interface GameItemOrderDetailMapper extends BaseMapper<GameItemOrderDetail> {

    @Select("select coalesce(sum(subtotal), 0) from game_item_order_details where order_id = #{orderId}")
    BigDecimal sumSubtotalByOrderId(@Param("orderId") Integer orderId);
}
