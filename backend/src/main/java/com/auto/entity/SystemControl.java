package com.auto.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Getter;
import lombok.Setter;

import java.time.LocalDateTime;

/** 中控系统级运行开关；当前使用 id=1 的单例记录。 */
@TableName("system_controls")
@Getter
@Setter
public class SystemControl {

    public static final int SINGLETON_ID = 1;

    @TableId(type = IdType.INPUT)
    private Integer id;

    private Integer autoGameTradeEnabled;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;
}
