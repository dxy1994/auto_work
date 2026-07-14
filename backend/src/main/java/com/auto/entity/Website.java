package com.auto.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.extension.handlers.JacksonTypeHandler;
import lombok.Getter;
import lombok.Setter;

import java.time.LocalDateTime;
import java.util.Map;

/** 网站。 */
@TableName(value = "websites", autoResultMap = true)
@Getter
@Setter
public class Website {

    @TableId(type = IdType.AUTO)
    private Integer id;

    private String name;

    private String url;

    private String icon;

    private String category;

    /** 登录类型：form / captcha / oauth。 */
    private String loginType = "form";

    @TableField(typeHandler = JacksonTypeHandler.class)
    private Map<String, Object> loginConfig;

    private String remark;

    private Integer sortOrder = 0;

    private Integer isActive = 1;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;
}
