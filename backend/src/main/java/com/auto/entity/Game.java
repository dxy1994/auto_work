package com.auto.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Getter;
import lombok.Setter;

import java.time.LocalDateTime;

/** 游戏。 */
@TableName("games")
@Getter
@Setter
public class Game {

    @TableId(type = IdType.AUTO)
    private Integer id;

    private String name;

    private String code;

    private String icon;

    private String platform;

    private String remark;

    /** web / script。 */
    private String tradeType = "script";

    /** 游戏 Worker 等待买家交易申请的最长秒数。 */
    private Integer tradeTimeoutSeconds = 300;

    private Integer sortOrder = 0;

    private Integer isActive = 1;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;
}
