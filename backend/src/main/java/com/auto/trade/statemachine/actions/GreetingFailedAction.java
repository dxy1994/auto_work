package com.auto.trade.statemachine.actions;

import com.auto.entity.GameItemOrder;
import com.auto.trade.statemachine.DeliveryState;
import com.auto.trade.statemachine.TransitionAction;

import java.util.Map;

/** 招呼执行失败：自转换，保持 greeting 等重试，无特殊副作用。 */
public class GreetingFailedAction implements TransitionAction {
    @Override
    public void execute(GameItemOrder order, DeliveryState from, DeliveryState to, Map<String, Object> context) {
        // 自转换，不改状态，仅记录事件（由状态机统一处理）
    }
}
