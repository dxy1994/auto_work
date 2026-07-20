package com.auto.trade.statemachine;

import com.auto.entity.GameItemOrder;
import com.auto.entity.TradeEvent;
import com.auto.service.GameItemOrderService;
import com.auto.service.TradeAssignmentService;
import com.auto.service.TradeEventService;
import com.auto.trade.statemachine.actions.*;
import com.auto.ws.AgentRegistry;
import com.auto.service.MachineService;
import com.auto.service.GameAccountService;
import com.auto.trade.TradeCompletionService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.HashMap;
import java.util.Map;
import java.util.Set;
import java.util.EnumSet;
import java.util.stream.Collectors;

/**
 * 订单交付状态机：集中管理所有合法状态转换及副作用。
 */
@Service
@Slf4j
public class OrderDeliveryStateMachine {

    private final Map<String, Transition> transitions = new HashMap<>();
    private final GameItemOrderService orderService;
    private final TradeEventService eventService;

    public OrderDeliveryStateMachine(
            GameItemOrderService orderService,
            TradeEventService eventService,
            TradeAssignmentService assignmentService,
            MachineService machineService,
            GameAccountService gameAccountService,
            AgentRegistry agentRegistry,
            TradeCompletionService tradeCompletionService) {

        this.orderService = orderService;
        this.eventService = eventService;

        // ── 注册所有合法转换 ──

        // 订单入库
        register(DeliveryState.DETECTED, DeliveryEvent.ORDER_DETECTED,
                DeliveryState.GREETING, new OrderDetectedAction());

        // 无招呼话术
        register(DeliveryState.GREETING, DeliveryEvent.NO_GREETING_SCRIPT,
                DeliveryState.GREETING_ABNORMAL,
                new NoGreetingScriptAction());

        // 无子订单
        register(DeliveryState.GREETING, DeliveryEvent.NO_SUB_ORDER,
                DeliveryState.GREETING_ABNORMAL,
                new NoSubOrderAction());

        // 招呼指令下发失败
        register(DeliveryState.GREETING, DeliveryEvent.GREETING_SEND_FAILED,
                DeliveryState.SUSPENDED,
                new GreetingSendFailedAction());

        // 招呼执行失败（保持 greeting，等重试）
        register(DeliveryState.GREETING, DeliveryEvent.GREETING_FAILED,
                DeliveryState.GREETING,
                new GreetingFailedAction());

        // 招呼成功 → 自动交易指派
        register(DeliveryState.GREETING, DeliveryEvent.GREETING_SUCCESS,
                DeliveryState.OFFERED,
                new GreetingSuccessAction());

        // Worker 接受 offer
        register(DeliveryState.OFFERED, DeliveryEvent.OFFER_ACCEPTED,
                DeliveryState.ASSIGNED,
                new OfferAcceptedAction(assignmentService));

        // Worker 拒绝 offer
        register(DeliveryState.OFFERED, DeliveryEvent.OFFER_REJECTED,
                DeliveryState.WAITING_ASSIGNMENT,
                new OfferRejectedAction(assignmentService, machineService, gameAccountService, agentRegistry));

        // Offer 过期
        register(DeliveryState.OFFERED, DeliveryEvent.OFFER_EXPIRED,
                DeliveryState.WAITING_ASSIGNMENT,
                new OfferExpiredAction(assignmentService, machineService, gameAccountService, agentRegistry));

        WorkerDisconnectedAction workerDisconnectedAction = new WorkerDisconnectedAction(
                assignmentService, machineService, gameAccountService, agentRegistry);
        register(DeliveryState.OFFERED, DeliveryEvent.WORKER_DISCONNECTED,
                DeliveryState.WAITING_ASSIGNMENT, workerDisconnectedAction);
        register(DeliveryState.ASSIGNED, DeliveryEvent.WORKER_DISCONNECTED,
                DeliveryState.WAITING_ASSIGNMENT, workerDisconnectedAction);

        // trade_start 下发失败
        register(DeliveryState.ASSIGNED, DeliveryEvent.START_FAILED,
                DeliveryState.SUSPENDED,
                new StartFailedAction(assignmentService, machineService, gameAccountService, agentRegistry));

        // 交易完成
        register(DeliveryState.ASSIGNED, DeliveryEvent.TRADE_COMPLETED,
                DeliveryState.COMPLETED,
                new TradeCompletedAction(assignmentService, machineService, gameAccountService,
                        agentRegistry, tradeCompletionService));

        // 交易取消
        register(DeliveryState.ASSIGNED, DeliveryEvent.TRADE_CANCELLED,
                DeliveryState.SUSPENDED,
                new TradeCancelledAction(assignmentService, machineService, gameAccountService, agentRegistry));

        // 手动重试指派
        register(DeliveryState.WAITING_ASSIGNMENT, DeliveryEvent.MANUAL_DISPATCH,
                DeliveryState.OFFERED,
                new ManualDispatchAction());

        // 人工修复后重置
        register(DeliveryState.GREETING_ABNORMAL, DeliveryEvent.RESET_TO_GREETING,
                DeliveryState.GREETING,
                new ResetToGreetingAction());
    }

    private void register(DeliveryState from, DeliveryEvent event,
                          DeliveryState to, TransitionAction action) {
        transitions.put(Transition.key(from, event), new Transition(from, event, to, action));
    }

    /**
     * 触发状态转换。
     *
     * @param order   当前订单
     * @param event   触发事件
     * @param context 附加参数（assignmentId、machineId、gameAccountId、errorCode、errorMessage 等）
     * @return 转换后的新状态
     */
    public DeliveryState fire(GameItemOrder order, DeliveryEvent event, Map<String, Object> context) {
        if (context == null) {
            context = Map.of();
        }
        DeliveryState current = DeliveryState.from(order.getDeliveryStatus(), order.getStatus());
        String key = Transition.key(current, event);
        Transition transition = transitions.get(key);
        if (transition == null) {
            throw new IllegalStateException(
                    "非法状态转换: " + current + " + " + event);
        }

        DeliveryState target = transition.to();

        log.info("[StateMachine] order_id={} {} + {} → {}",
                order.getId(), current, event, target);

        // 1. 执行副作用（更新 assignment、释放资源等）
        transition.action().execute(order, current, target, context);

        // 2. 统一更新 order 字段
        if (current != target) {
            order.setDeliveryStatus(target.getDeliveryStatus());
            order.setStatus(target.getOrderStatus());
        }
        // 设置错误码（如果 context 中提供）
        String errorCode = (String) context.get("errorCode");
        String errorMessage = (String) context.get("errorMessage");
        if (errorCode != null) {
            order.setLastErrorCode(errorCode);
            order.setLastErrorMessage(errorMessage);
        }

        // 3. 持久化
        orderService.updateById(order);

        // 4. 记录 TradeEvent
        recordEvent(order, event, current, target, context);

        return target;
    }

    /** 查询当前状态可触发的事件集合。 */
    public Set<DeliveryEvent> allowedEvents(DeliveryState state) {
        return transitions.values().stream()
                .filter(t -> t.from() == state)
                .map(Transition::event)
                .collect(Collectors.toCollection(() -> EnumSet.noneOf(DeliveryEvent.class)));
    }

    private void recordEvent(GameItemOrder order, DeliveryEvent event,
                             DeliveryState from, DeliveryState to, Map<String, Object> context) {
        try {
            TradeEvent te = new TradeEvent();
            te.setOrderId(order.getId());
            te.setAssignmentId((String) context.get("assignmentId"));
            te.setEventType(event.name().toLowerCase());
            te.setFromStatus(from.getDeliveryStatus());
            te.setToStatus(to.getDeliveryStatus());
            String message = (String) context.get("message");
            te.setMessage(message != null ? message : event.name());
            eventService.save(te);
        } catch (Exception e) {
            log.error("[StateMachine] 事件记录失败 order_id={} event={}: {}",
                    order.getId(), event, e.getMessage());
        }
    }
}
