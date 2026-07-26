package com.auto.trade;

import com.auto.entity.GameItemOrder;
import com.auto.entity.GameItemOrderDetail;
import com.auto.service.GameItemOrderDetailService;
import com.auto.service.GameItemOrderService;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Set;

/** 人工终结订单，并保证主订单、交付状态和子订单状态一致。 */
@Service
public class ManualOrderStatusService {

    private static final Set<String> ACTIVE_AUTOMATION = Set.of(
            "offered", "assigned");

    private final GameItemOrderService orderService;
    private final GameItemOrderDetailService detailService;
    private final TradeCompletionService completionService;

    public ManualOrderStatusService(
            GameItemOrderService orderService,
            GameItemOrderDetailService detailService,
            TradeCompletionService completionService) {
        this.orderService = orderService;
        this.detailService = detailService;
        this.completionService = completionService;
    }

    @Transactional
    public GameItemOrder complete(Integer orderId) {
        return completeInternal(orderId, true);
    }

    /** Worker 已收到停止指令后，由交易协调器完成终态落库。 */
    @Transactional
    public GameItemOrder completeAfterAutomationStopped(Integer orderId) {
        return completeInternal(orderId, false);
    }

    private GameItemOrder completeInternal(Integer orderId, boolean rejectActiveTrade) {
        GameItemOrder order = lockOrder(orderId);
        requireNotTerminal(order);
        if (rejectActiveTrade && ACTIVE_AUTOMATION.contains(order.getDeliveryStatus())) {
            throw new IllegalStateException("订单正在自动交易，不能直接标记完成");
        }

        completionService.complete(order);
        order.setDeliveryStatus("completed");
        order.setStatus("completed");
        if (order.getWebsiteConfirmedAt() == null) {
            order.setWebsiteConfirmedAt(LocalDateTime.now());
        }
        clearAutomationFields(order);
        orderService.updateById(order);
        return order;
    }

    @Transactional
    public GameItemOrder cancel(Integer orderId) {
        return cancelInternal(orderId, true);
    }

    /** Worker 已收到停止指令后，由交易协调器完成终态落库。 */
    @Transactional
    public GameItemOrder cancelAfterAutomationStopped(Integer orderId) {
        return cancelInternal(orderId, false);
    }

    private GameItemOrder cancelInternal(Integer orderId, boolean rejectActiveTrade) {
        GameItemOrder order = lockOrder(orderId);
        requireNotTerminal(order);
        if (rejectActiveTrade && ACTIVE_AUTOMATION.contains(order.getDeliveryStatus())) {
            throw new IllegalStateException("订单正在自动交易，请先停止并确认交易结果");
        }
        if (order.getGameDeliveredAt() != null || "wait_web_confirm".equals(order.getDeliveryStatus())) {
            throw new IllegalStateException("游戏内交易已经完成，不能取消订单，请标记为已完成");
        }

        List<GameItemOrderDetail> details = detailService.findByOrderId(orderId);
        for (GameItemOrderDetail detail : details) {
            detail.setStatus("cancelled");
            detailService.updateById(detail);
        }
        order.setDeliveryStatus("cancelled");
        order.setStatus("cancelled");
        clearAutomationFields(order);
        order.setLastErrorCode(null);
        order.setLastErrorMessage(null);
        orderService.updateById(order);
        return order;
    }

    private static void clearAutomationFields(GameItemOrder order) {
        order.setAssignmentId(null);
        order.setAssignedMachineId(null);
        order.setGameAccountId(null);
        order.setAssignedAt(null);
    }

    private GameItemOrder lockOrder(Integer orderId) {
        GameItemOrder order = orderService.getOne(
                new LambdaQueryWrapper<GameItemOrder>()
                        .eq(GameItemOrder::getId, orderId)
                        .last("FOR UPDATE"),
                false);
        if (order == null) {
            throw new IllegalArgumentException("订单不存在");
        }
        return order;
    }

    private static void requireNotTerminal(GameItemOrder order) {
        if ("completed".equals(order.getStatus()) || "cancelled".equals(order.getStatus())) {
            throw new IllegalStateException("订单已经是终态，不能重复操作");
        }
    }
}
