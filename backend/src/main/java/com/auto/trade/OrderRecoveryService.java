package com.auto.trade;

import com.auto.entity.GameItemOrder;
import com.auto.entity.GameItemOrderDetail;
import com.auto.service.GameItemOrderService;
import com.auto.trade.statemachine.DeliveryEvent;
import com.auto.trade.statemachine.OrderDeliveryStateMachine;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Map;

/** 按订单当前失败阶段恢复已确认成功步骤之后的流程。 */
@Service
public class OrderRecoveryService {

    private final GameItemOrderService orderService;
    private final OrderDetailGenerationService detailGenerationService;
    private final OrderDeliveryStateMachine stateMachine;

    public OrderRecoveryService(
            GameItemOrderService orderService,
            OrderDetailGenerationService detailGenerationService,
            OrderDeliveryStateMachine stateMachine) {
        this.orderService = orderService;
        this.detailGenerationService = detailGenerationService;
        this.stateMachine = stateMachine;
    }

    /** SUB_ORDER_MISSING：先恢复出错前状态，再事务性地重做子订单生成。 */
    @Transactional
    public List<GameItemOrderDetail> recoverMissingSubOrder(Integer orderId) {
        GameItemOrder order = orderService.getById(orderId);
        if (order == null) {
            throw new IllegalStateException("订单不存在");
        }
        if (!"greeting".equals(order.getDeliveryStatus())
                || !"abnormal".equals(order.getStatus())
                || !"SUB_ORDER_MISSING".equals(order.getLastErrorCode())) {
            throw new IllegalStateException("订单当前不是子订单生成失败状态");
        }

        // 出错前仍处于 greeting/pending，且招呼已经成功；这里只恢复状态，不发送招呼。
        stateMachine.fire(
                order,
                DeliveryEvent.RESET_TO_GREETING,
                Map.of("message", "恢复到子订单生成失败前的状态"));

        // 如果生成失败，整个事务回滚，订单仍保持原来的 greeting/abnormal。
        return detailGenerationService.ensureDetails(order);
    }
}
