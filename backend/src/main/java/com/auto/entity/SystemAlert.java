package com.auto.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Getter;
import lombok.Setter;

import java.time.LocalDateTime;

/** 可由总控用户手动关闭的系统运行提醒。 */
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
