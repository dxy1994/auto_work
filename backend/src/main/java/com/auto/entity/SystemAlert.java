package com.auto.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Getter;
import lombok.Setter;

import java.time.LocalDateTime;

/** 系统运行提醒；支持人工关闭，也可在对应故障恢复后自动关闭。 */
@TableName("system_alerts")
@Getter
@Setter
public class SystemAlert {

    @TableId(type = IdType.AUTO)
    private Long id;

    private String alertType;
    private String sourceKey;
    private Integer machineId;
    private Integer accountId;
    private String severity;
    private String title;
    private String message;
    private String status;
    private LocalDateTime occurredAt;
    private LocalDateTime dismissedAt;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
