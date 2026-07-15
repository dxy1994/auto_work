package com.auto.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.extension.handlers.Jackson3TypeHandler;
import lombok.Getter;
import lombok.Setter;

import java.time.LocalDateTime;

/** Cookies 存储（website_id + account_id 唯一）。 */
@TableName(value = "cookies_store", autoResultMap = true)
@Getter
@Setter
public class CookiesStore {

    @TableId(type = IdType.AUTO)
    private Integer id;

    private Integer websiteId;

    private Integer accountId;

    @TableField(typeHandler = Jackson3TypeHandler.class)
    private Object cookies;

    private LocalDateTime expiresAt;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;
}
