package com.auto.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Getter;
import lombok.Setter;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/** 库存变更审计日志。 */
@TableName("inventory_change_log")
@Getter
@Setter
public class InventoryChangeLog {

    @TableId(type = IdType.AUTO)
    private Integer id;

    private Integer inventoryId;

    private Integer gameId;

    private Integer regionId;

    private Integer itemId;

    /** stock_in / stock_out / price_update / fluctuation_update / system_sync / initialization */
    private String changeType;

    private Long stockBefore;

    private Long stockAfter;

    private Long stockDelta;

    /** 入库单价（仅入库时记录） */
    private BigDecimal unitPrice;

    /** 变更前均价 */
    private BigDecimal avgPriceBefore;

    /** 变更后均价 */
    private BigDecimal avgPriceAfter;

    /** 变更原因（出库时必填） */
    private String changeReason;

    private String operator;

    private Integer relatedOrderId;

    private LocalDateTime createdAt;
}
