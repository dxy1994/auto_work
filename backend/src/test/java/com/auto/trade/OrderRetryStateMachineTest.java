package com.auto.trade;

import com.auto.entity.GameItemOrder;
import com.auto.service.GameAccountService;
import com.auto.service.GameItemOrderService;
import com.auto.service.MachineService;
import com.auto.service.TradeAssignmentService;
import com.auto.service.TradeEventService;
import com.auto.trade.statemachine.DeliveryEvent;
import com.auto.trade.statemachine.DeliveryState;
import com.auto.trade.statemachine.OrderDeliveryStateMachine;
import com.auto.ws.AgentRegistry;
import org.junit.jupiter.api.Test;

import java.time.LocalDateTime;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;

class OrderRetryStateMachineTest {

    @Test
    void greetingFailureRestoresTheSameStateAndClearsTheError() {
        GameItemOrderService orderService = mock(GameItemOrderService.class);
        OrderDeliveryStateMachine stateMachine = stateMachine(orderService);
        GameItemOrder order = new GameItemOrder();
        order.setId(40);
        order.setDeliveryStatus("greeting");
        order.setStatus("pending");
        order.setLastErrorCode("GREETING_EXECUTION_FAILED");
        order.setLastErrorMessage("发送失败");

        DeliveryState target = stateMachine.fire(
                order,
                DeliveryEvent.RETRY_GREETING,
                Map.of("message", "恢复到出错前状态"));

        assertEquals(DeliveryState.GREETING, target);
        assertEquals("greeting", order.getDeliveryStatus());
        assertEquals("pending", order.getStatus());
        assertNull(order.getLastErrorCode());
        assertNull(order.getLastErrorMessage());
        verify(orderService).updateById(order);
    }

    @Test
    void assignmentFailureAfterGreetingRestoresBeforeRedispatch() {
        GameItemOrderService orderService = mock(GameItemOrderService.class);
        OrderDeliveryStateMachine stateMachine = stateMachine(orderService);
        GameItemOrder order = new GameItemOrder();
        order.setId(39);
        order.setDeliveryStatus("greeting");
        order.setStatus("pending");
        order.setLastErrorCode("TRADE_DISPATCH_FAILED");
        order.setLastErrorMessage("没有符合条件的交易机器");

        DeliveryState target = stateMachine.fire(
                order,
                DeliveryEvent.RETRY_ASSIGNMENT,
                Map.of("message", "恢复到交易指派出错前状态"));

        assertEquals(DeliveryState.WAITING_ASSIGNMENT, target);
        assertEquals("waiting_assignment", order.getDeliveryStatus());
        assertNull(order.getLastErrorCode());
        assertNull(order.getLastErrorMessage());
        verify(orderService).updateById(order);
    }

    @Test
    void subOrderFailureCanRestoreTheStateBeforeTheError() {
        GameItemOrderService orderService = mock(GameItemOrderService.class);
        OrderDeliveryStateMachine stateMachine = stateMachine(orderService);
        GameItemOrder order = new GameItemOrder();
        order.setId(41);
        order.setDeliveryStatus("greeting");
        order.setStatus("abnormal");
        order.setLastErrorCode("SUB_ORDER_MISSING");
        order.setLastErrorMessage("子订单缺失");

        DeliveryState target = stateMachine.fire(
                order,
                DeliveryEvent.RESET_TO_GREETING,
                Map.of("message", "恢复到出错前状态"));

        assertEquals(DeliveryState.GREETING, target);
        assertEquals("greeting", order.getDeliveryStatus());
        assertEquals("pending", order.getStatus());
        assertNull(order.getLastErrorCode());
        assertNull(order.getLastErrorMessage());
        verify(orderService).updateById(order);
    }

    @Test
    void suspendedFailureCanContinueFromWaitingAssignment() {
        GameItemOrderService orderService = mock(GameItemOrderService.class);
        OrderDeliveryStateMachine stateMachine = stateMachine(orderService);
        GameItemOrder order = new GameItemOrder();
        order.setId(42);
        order.setDeliveryStatus("suspended");
        order.setStatus("pending");
        order.setAssignmentId("assignment-1");
        order.setAssignedMachineId(7);
        order.setGameAccountId(9);
        order.setAssignedAt(LocalDateTime.now());
        order.setLastErrorCode("TRADE_EXECUTION_FAILED");
        order.setLastErrorMessage("执行失败");

        DeliveryState target = stateMachine.fire(
                order,
                DeliveryEvent.RETRY_ASSIGNMENT,
                Map.of("message", "人工重新尝试"));

        assertEquals(DeliveryState.WAITING_ASSIGNMENT, target);
        assertEquals("waiting_assignment", order.getDeliveryStatus());
        assertEquals("pending", order.getStatus());
        assertNull(order.getAssignmentId());
        assertNull(order.getAssignedMachineId());
        assertNull(order.getGameAccountId());
        assertNull(order.getAssignedAt());
        assertNull(order.getLastErrorCode());
        assertNull(order.getLastErrorMessage());
        verify(orderService).updateById(order);
    }

    @Test
    void busyMachineQueuesThenDequeuesOrderWithoutRepeatingGreeting() {
        GameItemOrderService orderService = mock(GameItemOrderService.class);
        OrderDeliveryStateMachine stateMachine = stateMachine(orderService);
        GameItemOrder order = new GameItemOrder();
        order.setId(43);
        order.setDeliveryStatus("greeting");
        order.setStatus("pending");

        DeliveryState queued = stateMachine.fire(
                order,
                DeliveryEvent.QUEUE_ASSIGNMENT,
                Map.of("machineId", 7, "gameAccountId", 9, "message", "进入队列"));

        assertEquals(DeliveryState.QUEUED, queued);
        assertEquals("queued", order.getDeliveryStatus());
        assertEquals(7, order.getAssignedMachineId());
        assertEquals(9, order.getGameAccountId());

        order.setAssignmentId("assignment-queue-1");
        DeliveryState offered = stateMachine.fire(
                order,
                DeliveryEvent.DEQUEUE_ASSIGNMENT,
                Map.of("assignmentId", "assignment-queue-1", "message", "队首开始指派"));

        assertEquals(DeliveryState.OFFERED, offered);
        assertEquals("offered", order.getDeliveryStatus());
    }

    private static OrderDeliveryStateMachine stateMachine(GameItemOrderService orderService) {
        return new OrderDeliveryStateMachine(
                orderService,
                mock(TradeEventService.class),
                mock(TradeAssignmentService.class),
                mock(MachineService.class),
                mock(GameAccountService.class),
                mock(AgentRegistry.class),
                mock(TradeCompletionService.class));
    }
}
