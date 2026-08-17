package com.auto.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Getter;
import lombok.Setter;

import java.time.LocalDateTime;

/** 系统告警产生、展示、播报和关闭的只追加审计事件。 */
@TableName("system_alert_events")
@Getter
@Setter
public class SystemAlertEvent {

    @TableId(type = IdType.AUTO)
    private Long id;

    private Long alertId;
    private String eventType;
    private LocalDateTime eventAt;
    private String actor;
    private String details;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;
}
