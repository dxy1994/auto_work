package com.auto.trade.statemachine.actions;

import com.auto.entity.GameItemOrder;
import com.auto.entity.TradeAssignment;
import com.auto.service.GameAccountService;
import com.auto.service.MachineService;
import com.auto.service.TradeAssignmentService;
import com.auto.trade.statemachine.DeliveryState;
import com.auto.trade.statemachine.TransitionAction;
import com.auto.ws.AgentRegistry;
import com.auto.trade.TradeCompletionService;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;

import java.time.LocalDateTime;
import java.util.Map;

/** 交易完成：结束 assignment、释放资源。 */
public class TradeCompletedAction implements TransitionAction {

    private final TradeAssignmentService assignmentService;
    private final MachineService machineService;
    private final GameAccountService gameAccountService;
    private final AgentRegistry agentRegistry;
    private final TradeCompletionService tradeCompletionService;

    public TradeCompletedAction(TradeAssignmentService assignmentService,
                                MachineService machineService,
                                GameAccountService gameAccountService,
                                AgentRegistry agentRegistry,
                                TradeCompletionService tradeCompletionService) {
        this.assignmentService = assignmentService;
        this.machineService = machineService;
        this.gameAccountService = gameAccountService;
        this.agentRegistry = agentRegistry;
        this.tradeCompletionService = tradeCompletionService;
    }

    @Override
    public void execute(GameItemOrder order, DeliveryState from, DeliveryState to, Map<String, Object> context) {
        String assignmentId = (String) context.get("assignmentId");
        int machineId = ((Number) context.get("machineId")).intValue();
        int gameAccountId = ((Number) context.get("gameAccountId")).intValue();

        tradeCompletionService.complete(order);
        finishAssignment(assignmentId, "completed");
        ResourceHelper.release(machineService, gameAccountService, agentRegistry, machineId, gameAccountId);
    }

    private void finishAssignment(String assignmentId, String status) {
        TradeAssignment assignment = assignmentService.getOne(
                new LambdaQueryWrapper<TradeAssignment>()
                        .eq(TradeAssignment::getAssignmentId, assignmentId), false);
        if (assignment != null) {
            assignment.setStatus(status);
            assignment.setFinishedAt(LocalDateTime.now());
            assignmentService.updateById(assignment);
        }
    }
}
