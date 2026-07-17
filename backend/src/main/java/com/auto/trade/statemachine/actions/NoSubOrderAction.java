package com.auto.trade.statemachine.actions;

import com.auto.entity.GameItemOrder;
import com.auto.trade.statemachine.DeliveryState;
import com.auto.trade.statemachine.TransitionAction;

import java.util.Map;

/** 招呼成功但无子订单：设置异常错误码。 */
public class NoSubOrderAction implements TransitionAction {
    @Override
    public void execute(GameItemOrder order, DeliveryState from, DeliveryState to, Map<String, Object> context) {
        order.setLastErrorCode("SUB_ORDER_MISSING");
        order.setLastErrorMessage("招呼成功但子订单未解析，请人工处理");
    }
}
