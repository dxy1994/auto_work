package com.auto.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Getter;
import lombok.Setter;

import java.time.LocalDateTime;

/** 大区话术。 */
@TableName("region_scripts")
@Getter
@Setter
public class RegionScript {

    @TableId(type = IdType.AUTO)
    private Integer id;

    private Integer regionId;

    /** 关联游戏话术ID。 */
    private Integer gameScriptId;

    private String title;

    private String content;

    private String positionImage;

    private String category;

    private Integer sortOrder = 0;

    private Integer isActive = 1;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;
}
