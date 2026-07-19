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

/** 大区库存商铺定价（inventory_id + account_id 唯一）。 */
@TableName("game_region_inventory_shop_price")
@Getter
@Setter
public class GameRegionInventoryShopPrice {

    @TableId(type = IdType.AUTO)
    private Integer id;

    private Integer inventoryId;

    private Integer accountId;

    private BigDecimal sellingPrice = BigDecimal.ZERO;

    private BigDecimal minSellingPrice = BigDecimal.ZERO;

    private BigDecimal maxSellingPrice = BigDecimal.ZERO;

    private Integer isActive = 1;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;
}
