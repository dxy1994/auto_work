package com.auto.trade.statemachine.actions;

import com.auto.entity.GameItemOrder;
import com.auto.entity.TradeAssignment;
import com.auto.service.GameAccountService;
import com.auto.service.MachineService;
import com.auto.service.TradeAssignmentService;
import com.auto.trade.GameDeliveryConfirmationRequested;
import com.auto.trade.TradeCompletionService;
import com.auto.trade.statemachine.DeliveryState;
import com.auto.trade.statemachine.TransitionAction;
import com.auto.ws.AgentRegistry;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import org.springframework.context.ApplicationEventPublisher;

import java.time.LocalDateTime;
import java.util.Map;

/** 游戏交易已完成：扣减游戏库存并释放 Worker，订单等待网站确认。 */
public class GameTradeCompletedAction implements TransitionAction {

    private final TradeAssignmentService assignmentService;
    private final MachineService machineService;
    private final GameAccountService gameAccountService;
    private final AgentRegistry agentRegistry;
    private final TradeCompletionService tradeCompletionService;
    private final ApplicationEventPublisher eventPublisher;

    public GameTradeCompletedAction(
            TradeAssignmentService assignmentService,
            MachineService machineService,
            GameAccountService gameAccountService,
            AgentRegistry agentRegistry,
            TradeCompletionService tradeCompletionService,
            ApplicationEventPublisher eventPublisher) {
        this.assignmentService = assignmentService;
        this.machineService = machineService;
        this.gameAccountService = gameAccountService;
        this.agentRegistry = agentRegistry;
        this.tradeCompletionService = tradeCompletionService;
        this.eventPublisher = eventPublisher;
    }

    @Override
    public void execute(
            GameItemOrder order,
            DeliveryState from,
            DeliveryState to,
            Map<String, Object> context) {
        String assignmentId = (String) context.get("assignmentId");
        int machineId = ((Number) context.get("machineId")).intValue();
        int gameAccountId = ((Number) context.get("gameAccountId")).intValue();

        tradeCompletionService.gameDelivered(order);
        TradeAssignment assignment = assignmentService.getOne(
                new LambdaQueryWrapper<TradeAssignment>()
                        .eq(TradeAssignment::getAssignmentId, assignmentId), false);
        if (assignment != null) {
            assignment.setStatus("wait_web_confirm");
            assignment.setFinishedAt(LocalDateTime.now());
            assignmentService.updateById(assignment);
        }
        ResourceHelper.release(
                machineService, gameAccountService, agentRegistry, machineId, gameAccountId);
        eventPublisher.publishEvent(new GameDeliveryConfirmationRequested(order.getId()));
    }
}
