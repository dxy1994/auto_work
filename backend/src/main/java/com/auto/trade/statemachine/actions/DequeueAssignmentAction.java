package com.auto.trade.statemachine.actions;

import com.auto.entity.GameItemOrder;
import com.auto.trade.statemachine.DeliveryState;
import com.auto.trade.statemachine.TransitionAction;

import java.util.Map;

/** 队首订单开始指派；机器和账号已由队列目标确定。 */
public class DequeueAssignmentAction implements TransitionAction {

    @Override
    public void execute(GameItemOrder order, DeliveryState from, DeliveryState to, Map<String, Object> context) {
        order.setLastErrorCode(null);
        order.setLastErrorMessage(null);
    }
}
