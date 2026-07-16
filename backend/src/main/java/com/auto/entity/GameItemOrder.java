package com.auto.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.annotation.Version;
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

    private Integer websiteId;

    private String sourceOrderNo;

    private Integer gameId;

    private Integer regionId;

    private Integer gameAccountId;

    private String buyerCharacter;

    private String assetType = "adena";

    private BigDecimal assetAmount;

    private String deliveryStatus = "detected";

    private String assignmentId;

    @Version
    private Integer rowVersion = 0;

    private String customerName;

    private String customerContact;

    private BigDecimal totalAmount = BigDecimal.ZERO;

    /** pending / assigned / processing / completed / cancelled。 */
    private String status = "pending";

    private Integer assignedMachineId;

    private LocalDateTime assignedAt;

    private LocalDateTime completedAt;

    private LocalDateTime gameDeliveredAt;

    private LocalDateTime websiteConfirmedAt;

    private String lastErrorCode;

    private String lastErrorMessage;

    private String remark;

    /** 平台原始下单时间（Marketplace 采集） */
    private LocalDateTime platformOrderTime;

    /** 平台售价-원（Marketplace 采集） */
    private BigDecimal platformPrice;

    /** 平台物品分类-게임머니/아이템/계정（Marketplace 采集） */
    private String platformItemType;

    /** 平台商品标题（Marketplace 采集） */
    private String productTitle;

    /** 上架数量（Marketplace 采集） */
    private Integer quantity;

    /** 已售数量（Marketplace 采集） */
    private Integer saleQuantity;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;
}
