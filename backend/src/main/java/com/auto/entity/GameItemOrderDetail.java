package com.auto.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Getter;
import lombok.Setter;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/** 游戏物品订单明细。 */
@TableName("game_item_order_details")
@Getter
@Setter
public class GameItemOrderDetail {

    @TableId(type = IdType.AUTO)
    private Integer id;

    private Integer orderId;

    private Integer itemId;

    private String itemName;

    private String itemImage;

    private Integer quantity = 1;

    private BigDecimal unitPrice = BigDecimal.ZERO;

    private BigDecimal subtotal = BigDecimal.ZERO;

    private BigDecimal purchasePrice;

    private BigDecimal sellingPrice;

    /** pending / processing / completed / failed。 */
    private String status = "pending";

    private String remark;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;
}
