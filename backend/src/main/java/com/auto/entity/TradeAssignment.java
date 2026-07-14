package com.auto.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Getter;
import lombok.Setter;

import java.time.LocalDateTime;

/** 总控向 Worker 发出的自动交易指派。 */
@TableName("trade_assignments")
@Getter
@Setter
public class TradeAssignment {

    @TableId(type = IdType.AUTO)
    private Integer id;
    private String assignmentId;
    private Integer orderId;
    private Integer machineId;
    private Integer gameAccountId;
    private String status;
    private String tokenHash;
    private LocalDateTime leaseExpiresAt;
    private String rejectReason;
    private LocalDateTime acceptedAt;
    private LocalDateTime startedAt;
    private LocalDateTime finishedAt;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;
}
