package com.auto.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.extension.handlers.Jackson3TypeHandler;
import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Getter;
import lombok.Setter;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

/** 游戏账号。 */
@TableName(value = "game_accounts", autoResultMap = true)
@Getter
@Setter
public class GameAccount {

    @TableId(type = IdType.AUTO)
    private Integer id;

    private Integer gameId;

    private Integer regionId;

    private Integer machineId;

    private String accountName;

    /** 账号（加密存储）。 */
    private String accountNo;

    /** 密码（加密存储）。 */
    @JsonProperty(access = JsonProperty.Access.WRITE_ONLY)
    private String password;

    private String nickname;

    private String level;

    @TableField(typeHandler = Jackson3TypeHandler.class)
    private Map<String, Object> extraFields;

    /** idle / in_use / locked / disabled。 */
    private String status = "idle";

    /** 大区ID列表（瞬态，不持久化到本表，通过 game_account_regions 维护）。 */
    @TableField(exist = false)
    private List<Integer> regionIds;

    private Integer isActive = 1;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;
}
