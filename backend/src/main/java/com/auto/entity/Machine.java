package com.auto.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Getter;
import lombok.Setter;

import java.time.LocalDateTime;

/** 执行机器（worker）。 */
@TableName("machines")
@Getter
@Setter
public class Machine {

    @TableId(type = IdType.AUTO)
    private Integer id;

    private String macAddress;

    private String hostname;

    private String ipAddress;

    private String name;

    private String osInfo;

    /** online / offline / busy / disabled。 */
    private String status = "offline";

    private LocalDateTime lastHeartbeat;

    private String remark;

    private Integer isActive = 1;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;
}
