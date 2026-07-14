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

/** 游戏物品（支持套装父子结构）。 */
@TableName("game_items")
@Getter
@Setter
public class GameItem {

    @TableId(type = IdType.AUTO)
    private Integer id;

    private Integer gameId;

    /** 父物品ID（套装子物品）。 */
    private Integer parentId;

    private String name;

    private String code;

    private String image;

    private Integer isBundle = 0;

    private String category;

    private BigDecimal price = BigDecimal.ZERO;

    private String remark;

    private Integer sortOrder = 0;

    private Integer isActive = 1;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;
}
