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
    private Integer occurrenceCount;
    private LocalDateTime occurredAt;
    private LocalDateTime lastOccurredAt;
    private LocalDateTime dismissedAt;
    private Integer presentationCount;
    private LocalDateTime lastPresentedAt;
    private Integer voiceNotificationCount;
    private LocalDateTime lastVoiceNotifiedAt;
    private String closeType;
    private String closeReason;
    private String closedBy;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
