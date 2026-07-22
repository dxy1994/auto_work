package com.auto.trade.statemachine.actions;

import com.auto.entity.GameItemOrder;
import com.auto.trade.statemachine.DeliveryState;
import com.auto.trade.statemachine.TransitionAction;

import java.util.Map;

/** 招呼指令下发失败（机器离线）。 */
public class GreetingSendFailedAction implements TransitionAction {
    @Override
    public void execute(GameItemOrder order, DeliveryState from, DeliveryState to, Map<String, Object> context) {
        order.setLastErrorCode("GREETING_FAILED");
        order.setLastErrorMessage("原因：监控机器离线，招呼指令无法下发。解决方案：确认监控端已启动并连接总控，然后重试招呼。");
    }
}
