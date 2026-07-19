package com.auto.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Getter;
import lombok.Setter;

import java.time.LocalDateTime;

/** 平台定时调度配置（account_id + code 唯一）。 */
@TableName("platform_schedules")
@Getter
@Setter
public class PlatformSchedule {

    @TableId(type = IdType.AUTO)
    private Integer id;

    private Integer accountId;

    private String name;

    private String code;

    /** 刷新频率(秒)，-1 表示无需刷新。 */
    private Integer refreshInterval = -1;

    /** 定时类型：none / once / scheduled。 */
    private String scheduleType = "none";

    private LocalDateTime scheduleTime;

    /** schedule_type=scheduled 时的执行间隔(秒)，字符串存储。 */
    private String scheduleCron;

    private String alertAudioPath;

    private Integer isEnabled = 1;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;
}
