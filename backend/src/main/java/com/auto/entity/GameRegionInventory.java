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

/** 大区物品库存（region_id + item_id 唯一）。 */
@TableName("game_region_inventory")
@Getter
@Setter
public class GameRegionInventory {

    @TableId(type = IdType.AUTO)
    private Integer id;

    private Integer gameId;

    private Integer regionId;

    private Integer itemId;

    private Integer stock = 0;

    private BigDecimal purchasePrice = BigDecimal.ZERO;

    private BigDecimal maxFluctuation;

    private BigDecimal maxFluctuationRate;

    private Integer isActive = 1;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;
}
