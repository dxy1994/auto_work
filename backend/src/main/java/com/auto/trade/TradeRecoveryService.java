package com.auto.trade;

import com.auto.entity.GameItemOrder;
import com.auto.entity.TradeAssignment;
import com.auto.service.GameItemOrderService;
import com.auto.service.TradeAssignmentService;
import com.auto.trade.statemachine.DeliveryEvent;
import com.auto.trade.statemachine.OrderDeliveryStateMachine;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

/** 将断线或后端重启遗留的活动指派恢复为可重新指派状态。 */
@Service
@Slf4j
public class TradeRecoveryService {

    private static final List<String> ACTIVE_ASSIGNMENT_STATUSES = List.of(
            "offered", "accepted", "started", "preparing", "switching_region",
            "waiting_buyer", "waiting_buyer_review", "trading", "verifying");

    private final TradeAssignmentService assignmentService;
    private final GameItemOrderService orderService;
    private final OrderDeliveryStateMachine stateMachine;

    public TradeRecoveryService(TradeAssignmentService assignmentService,
                                GameItemOrderService orderService,
                                OrderDeliveryStateMachine stateMachine) {
        this.assignmentService = assignmentService;
        this.orderService = orderService;
        this.stateMachine = stateMachine;
    }

    @EventListener(ApplicationReadyEvent.class)
    @Transactional
    public void recoverAfterRestart() {
        List<TradeAssignment> active = assignmentService.list(
                new LambdaQueryWrapper<TradeAssignment>()
                        .in(TradeAssignment::getStatus, activeAssignmentStatuses()));
        for (TradeAssignment assignment : active) {
            recover(assignment, "backend restarted");
        }
    }

    @EventListener
    @Transactional
    public void recoverLostMachine(MachineSessionLost event) {
        List<TradeAssignment> active = assignmentService.list(
                new LambdaQueryWrapper<TradeAssignment>()
                        .eq(TradeAssignment::getMachineId, event.machineId())
                        .in(TradeAssignment::getStatus, activeAssignmentStatuses()));
        for (TradeAssignment assignment : active) {
            recover(assignment, event.reason());
        }
    }

    void recover(TradeAssignment assignment, String reason) {
        if ("pending".equals(assignment.getBuyerReviewStatus())) {
            assignment.setBuyerReviewStatus("cancelled");
            assignment.setBuyerReviewDecidedAt(java.time.LocalDateTime.now());
            assignmentService.updateById(assignment);
        }
        GameItemOrder order = orderService.getById(assignment.getOrderId());
        if (order == null) {
            log.warn("[TradeRecovery] 指派对应订单不存在 assignment_id={}",
                    assignment.getAssignmentId());
            return;
        }
        if (!"offered".equals(order.getDeliveryStatus())
                && !"assigned".equals(order.getDeliveryStatus())) {
            log.info("[TradeRecovery] 订单已不在活动态，跳过 assignment_id={} delivery_status={}",
                    assignment.getAssignmentId(), order.getDeliveryStatus());
            return;
        }

        Map<String, Object> context = new HashMap<>();
        context.put("assignmentId", assignment.getAssignmentId());
        context.put("machineId", assignment.getMachineId());
        context.put("gameAccountId", assignment.getGameAccountId());
        context.put("reason", "worker_session_lost");
        context.put("message", reason);
        context.put("errorCode", "WORKER_DISCONNECTED");
        context.put("errorMessage", reason);
        boolean resultMayBeUncertain = "trading".equals(assignment.getStatus())
                || "verifying".equals(assignment.getStatus());
        if (resultMayBeUncertain) {
            context.put("assignmentStatus", "interrupted_uncertain");
            context.put("errorCode", "WORKER_DISCONNECTED_RESULT_UNCERTAIN");
            stateMachine.fire(order, DeliveryEvent.TRADE_VERIFICATION_FAILED, context);
        } else {
            stateMachine.fire(order, DeliveryEvent.WORKER_DISCONNECTED, context);
        }
    }

    private static List<String> activeAssignmentStatuses() {
        return ACTIVE_ASSIGNMENT_STATUSES;
    }
}
