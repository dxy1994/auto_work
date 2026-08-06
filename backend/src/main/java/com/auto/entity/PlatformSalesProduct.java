package com.auto.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Getter;
import lombok.Setter;

import java.time.LocalDateTime;

/** 平台账号当前实际在售的商品镜像。 */
@TableName("platform_sales_products")
@Getter
@Setter
public class PlatformSalesProduct {

    @TableId(type = IdType.AUTO)
    private Integer id;

    private Integer websiteId;

    private Integer platformAccountId;

    private String platform;

    private String platformProductId;

    private String platformItemType;

    private Integer gameId;

    private Integer regionId;

    private Integer gameItemId;

    /** 平台页面原始游戏名。 */
    private String gameName;

    /** 平台页面原始大区/服务器名。 */
    private String regionName;

    private String title;

    /** 从标题的 %物品名% 标记中提取的实际商品。 */
    private String parsedItemName;

    /** matched / title_parse_failed / game_unmatched / region_unmatched / item_unmatched。 */
    private String parseStatus;

    private String parseError;

    private String quantityText;

    private String priceText;

    private String platformRegisteredAt;

    /** 从平台数量文本解析出的比对值；范围数量取上限。 */
    @TableField(exist = false)
    private Long parsedQuantity;

    @TableField(exist = false)
    private Integer inventoryId;

    @TableField(exist = false)
    private Long inventoryStock;

    /** matched / mismatch / quantity_unavailable / inventory_missing / not_matched。 */
    @TableField(exist = false)
    private String inventoryComparisonStatus;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;
}
