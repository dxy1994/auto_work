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

/** 游戏物品订单主表。 */
@TableName("game_item_orders")
@Getter
@Setter
public class GameItemOrder {

    @TableId(type = IdType.AUTO)
    private Integer id;

    private String orderNo;

    private Integer gameId;

    private Integer regionId;

    private String customerName;

    private String customerContact;

    private BigDecimal totalAmount = BigDecimal.ZERO;

    /** pending / assigned / processing / completed / cancelled。 */
    private String status = "pending";

    private Integer assignedMachineId;

    private LocalDateTime assignedAt;

    private LocalDateTime completedAt;

    private String remark;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;
}
