package com.auto.trade.statemachine.actions;

import com.auto.entity.GameItemOrder;
import com.auto.trade.statemachine.DeliveryState;
import com.auto.trade.statemachine.TransitionAction;

import java.util.Map;

/** 招呼成功：无特殊副作用，由调用方负责后续交易指派。 */
public class GreetingSuccessAction implements TransitionAction {
    @Override
    public void execute(GameItemOrder order, DeliveryState from, DeliveryState to, Map<String, Object> context) {
        order.setLastErrorCode(null);
        order.setLastErrorMessage(null);
    }
}
