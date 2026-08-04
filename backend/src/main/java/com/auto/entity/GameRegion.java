package com.auto.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Getter;
import lombok.Setter;

import java.time.LocalDateTime;

/** 游戏大区。 */
@TableName("game_regions")
@Getter
@Setter
public class GameRegion {

    @TableId(type = IdType.AUTO)
    private Integer id;

    private Integer gameId;

    private String name;

    private String code;

    private Integer sortOrder;

    /** 1280x960 游戏客户区内的大区选择点击坐标。 */
    private Integer selectX;

    private Integer selectY;

    /** 大区在游戏客户端服务器列表中的页码，从 1 开始。 */
    private Integer selectPage = 1;

    private Integer isActive = 1;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;
}
