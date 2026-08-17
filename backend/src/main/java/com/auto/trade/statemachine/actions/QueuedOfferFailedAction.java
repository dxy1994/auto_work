package com.auto.trade.statemachine.actions;

import com.auto.entity.GameItemOrder;
import com.auto.entity.TradeAssignment;
import com.auto.service.GameAccountService;
import com.auto.service.MachineService;
import com.auto.service.TradeAssignmentService;
import com.auto.trade.statemachine.DeliveryState;
import com.auto.trade.statemachine.TransitionAction;
import com.auto.ws.AgentRegistry;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;

import java.time.LocalDateTime;
import java.util.Map;

/** 队首 offer 尚未真正执行时失败，释放预占并放回原机器队首等待重试。 */
public class QueuedOfferFailedAction implements TransitionAction {

    private final TradeAssignmentService assignmentService;
    private final MachineService machineService;
    private final GameAccountService gameAccountService;
    private final AgentRegistry agentRegistry;

    public QueuedOfferFailedAction(TradeAssignmentService assignmentService,
                                   MachineService machineService,
                                   GameAccountService gameAccountService,
                                   AgentRegistry agentRegistry) {
        this.assignmentService = assignmentService;
        this.machineService = machineService;
        this.gameAccountService = gameAccountService;
        this.agentRegistry = agentRegistry;
    }

    @Override
    public void execute(GameItemOrder order, DeliveryState from, DeliveryState to, Map<String, Object> context) {
        String assignmentId = (String) context.get("assignmentId");
        TradeAssignment assignment = assignmentService.getOne(
                new LambdaQueryWrapper<TradeAssignment>()
                        .eq(TradeAssignment::getAssignmentId, assignmentId), false);
        if (assignment != null) {
            assignment.setStatus((String) context.getOrDefault("assignmentStatus", "queue_retry"));
            assignment.setRejectReason((String) context.get("reason"));
            assignment.setFinishedAt(LocalDateTime.now());
            assignmentService.updateById(assignment);
        }

        Number machineId = (Number) context.get("machineId");
        Number gameAccountId = (Number) context.get("gameAccountId");
        if (machineId != null && gameAccountId != null) {
            ResourceHelper.release(machineService, gameAccountService, agentRegistry,
                    machineId.intValue(), gameAccountId.intValue());
        }
        order.setAssignmentId(null);
        order.setAssignedAt(null);
        order.setLastErrorCode(null);
        order.setLastErrorMessage(null);
    }
}
