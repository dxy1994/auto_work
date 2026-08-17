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
        order.setLastErrorMessage("原因：当前网站或游戏未配置可用的招呼话术。解决方案：在招呼话术管理中新增并启用匹配的话术，然后重试该订单。");
    }
}
