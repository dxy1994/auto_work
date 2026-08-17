package com.auto.trade.statemachine.actions;

import com.auto.entity.GameItemOrder;
import com.auto.trade.statemachine.DeliveryState;
import com.auto.trade.statemachine.TransitionAction;

import java.util.Map;

/** 明确失败后的人工重试：清理旧指派信息，从待指派阶段继续。 */
public class RetryAssignmentAction implements TransitionAction {
    @Override
    public void execute(
            GameItemOrder order,
            DeliveryState from,
            DeliveryState to,
            Map<String, Object> context) {
        order.setAssignmentId(null);
        order.setAssignedMachineId(null);
        order.setGameAccountId(null);
        order.setAssignedAt(null);
        order.setLastErrorCode(null);
        order.setLastErrorMessage(null);
    }
}
