package com.auto.trade.statemachine.actions;

import com.auto.entity.GameItemOrder;
import com.auto.trade.statemachine.DeliveryState;
import com.auto.trade.statemachine.TransitionAction;

import java.util.Map;

/** 无招呼话术：设置异常错误码。 */
public class NoGreetingScriptAction implements TransitionAction {
    @Override
    public void execute(GameItemOrder order, DeliveryState from, DeliveryState to, Map<String, Object> context) {
        order.setLastErrorCode("NO_GREETING_SCRIPT");
        order.setLastErrorMessage("未找到招呼话术，请人工处理");
    }
}
