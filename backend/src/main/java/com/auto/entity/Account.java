package com.auto.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.extension.handlers.JacksonTypeHandler;
import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Getter;
import lombok.Setter;

import java.time.LocalDateTime;
import java.util.Map;

/** 网站账号。 */
@TableName(value = "accounts", autoResultMap = true)
@Getter
@Setter
public class Account {

    @TableId(type = IdType.AUTO)
    private Integer id;

    private Integer websiteId;

    private String label;

    private String username;

    /** AES 加密存储。 */
    @JsonProperty(access = JsonProperty.Access.WRITE_ONLY)
    private String password;

    @TableField(typeHandler = JacksonTypeHandler.class)
    private Map<String, Object> extraFields;

    private Integer isDefault = 0;

    private Integer isActive = 1;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;
}
