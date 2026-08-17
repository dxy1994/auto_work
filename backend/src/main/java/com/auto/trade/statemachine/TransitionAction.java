package com.auto.trade.statemachine;

import com.auto.entity.GameItemOrder;

import java.util.Map;

/**
 * 状态转换副作用接口。
 *
 * <p>每个 Action 只处理该转换特有的副作用（更新 assignment、释放资源等），
 * 通用的 order 字段更新和 TradeEvent 记录由状态机统一处理。
 */
public interface TransitionAction {

    /**
     * 执行转换副作用。
     *
     * @param order   当前订单（可修改字段，状态机会随后持久化）
     * @param from    转换前状态
     * @param to      转换后状态
     * @param context 调用方传入的附加参数（assignmentId、machineId 等）
     */
    void execute(GameItemOrder order, DeliveryState from, DeliveryState to, Map<String, Object> context);
}
