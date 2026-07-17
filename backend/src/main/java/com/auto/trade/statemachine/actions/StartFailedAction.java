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

/** trade_start 下发失败：结束 assignment、释放资源。 */
public class StartFailedAction implements TransitionAction {

    private final TradeAssignmentService assignmentService;
    private final MachineService machineService;
    private final GameAccountService gameAccountService;
    private final AgentRegistry agentRegistry;

    public StartFailedAction(TradeAssignmentService assignmentService,
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
        int machineId = ((Number) context.get("machineId")).intValue();
        int gameAccountId = ((Number) context.get("gameAccountId")).intValue();

        finishAssignment(assignmentId, "start_failed");
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
