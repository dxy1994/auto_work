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
        order.setLastErrorMessage("原因：招呼成功，但未生成任何子订单，可能是 %物品名或编码% 未匹配启用物品，或套装未配置子物品。"
                + "解决方案：检查平台标题中的 %物品名或编码%，确认游戏物品管理中存在名称或编码匹配的启用物品；若为套装，请配置套装子物品后重试。");
    }
}
