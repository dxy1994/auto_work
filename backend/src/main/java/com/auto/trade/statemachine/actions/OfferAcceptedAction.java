package com.auto.trade.statemachine.actions;

import com.auto.entity.GameItemOrder;
import com.auto.entity.TradeAssignment;
import com.auto.service.TradeAssignmentService;
import com.auto.trade.statemachine.DeliveryState;
import com.auto.trade.statemachine.TransitionAction;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;

import java.time.LocalDateTime;
import java.util.Map;

/** Worker 接受 offer：更新 assignment 状态为 accepted。 */
public class OfferAcceptedAction implements TransitionAction {

    private final TradeAssignmentService assignmentService;

    public OfferAcceptedAction(TradeAssignmentService assignmentService) {
        this.assignmentService = assignmentService;
    }

    @Override
    public void execute(GameItemOrder order, DeliveryState from, DeliveryState to, Map<String, Object> context) {
        String assignmentId = (String) context.get("assignmentId");
        if (assignmentId == null) return;

        TradeAssignment assignment = assignmentService.getOne(
                new LambdaQueryWrapper<TradeAssignment>()
                        .eq(TradeAssignment::getAssignmentId, assignmentId), false);
        if (assignment != null) {
            assignment.setStatus("accepted");
            assignment.setAcceptedAt(LocalDateTime.now());
            assignmentService.updateById(assignment);
        }
    }
}
