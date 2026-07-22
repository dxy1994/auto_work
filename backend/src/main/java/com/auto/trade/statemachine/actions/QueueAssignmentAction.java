package com.auto.trade.statemachine.actions;

import com.auto.entity.GameItemOrder;
import com.auto.trade.statemachine.DeliveryState;
import com.auto.trade.statemachine.TransitionAction;

import java.util.Map;

/** 将订单绑定到忙碌机器的 FIFO 队列，但不预占机器或游戏账号。 */
public class QueueAssignmentAction implements TransitionAction {

    @Override
    public void execute(GameItemOrder order, DeliveryState from, DeliveryState to, Map<String, Object> context) {
        Number machineId = (Number) context.get("machineId");
        Number gameAccountId = (Number) context.get("gameAccountId");
        if (machineId == null || gameAccountId == null) {
            throw new IllegalStateException("排队订单缺少目标机器或游戏账号");
        }
        order.setAssignmentId(null);
        order.setAssignedMachineId(machineId.intValue());
        order.setGameAccountId(gameAccountId.intValue());
        order.setAssignedAt(null);
        order.setLastErrorCode(null);
        order.setLastErrorMessage(null);
    }
}
