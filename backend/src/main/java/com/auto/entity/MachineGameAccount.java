package com.auto.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Getter;
import lombok.Setter;

import java.time.LocalDateTime;

/** 机器关联游戏账号。 */
@TableName("machine_game_accounts")
@Getter
@Setter
public class MachineGameAccount {

    @TableId(type = IdType.AUTO)
    private Integer id;

    private Integer machineId;

    private Integer gameAccountId;

    private Integer priority = 0;

    private Integer maxConcurrent = 1;

    private Integer isActive = 1;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;
}
