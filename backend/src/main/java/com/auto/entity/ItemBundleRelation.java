package com.auto.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Getter;
import lombok.Setter;

import java.time.LocalDateTime;

/** 套装-物品多对多关联。 */
@TableName("item_bundle_relations")
@Getter
@Setter
public class ItemBundleRelation {

    @TableId(type = IdType.AUTO)
    private Integer id;

    private Integer bundleId;

    private Integer itemId;

    private Integer quantity = 1;

    private Integer sortOrder = 0;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;
}
