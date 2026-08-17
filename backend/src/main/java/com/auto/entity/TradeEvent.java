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
import java.util.Map;

/** 只追加的自动交易生命周期事件。 */
@TableName(value = "trade_events", autoResultMap = true)
@Getter
@Setter
public class TradeEvent {

    @TableId(type = IdType.AUTO)
    private Long id;
    private Integer orderId;
    private String assignmentId;
    private String eventType;
    private String fromStatus;
    private String toStatus;
    private String message;

    @TableField(typeHandler = Jackson3TypeHandler.class)
    private Map<String, Object> payload;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;
}
