package com.auto.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Getter;
import lombok.Setter;

import java.time.LocalDateTime;

/** 登录日志。 */
@TableName("login_logs")
@Getter
@Setter
public class LoginLog {

    @TableId(type = IdType.AUTO)
    private Integer id;

    private Integer websiteId;

    private Integer accountId;

    /** success / failed / captcha_required / timeout。 */
    private String status;

    private String message;

    private Integer durationMs;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;
}
