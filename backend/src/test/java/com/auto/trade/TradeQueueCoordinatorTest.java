package com.auto.trade;

import com.auto.entity.Game;
import com.auto.entity.GameAccount;
import com.auto.entity.GameItemOrder;
import com.auto.entity.MachineGameAccount;
import com.auto.entity.TradeAssignment;
import com.auto.service.GameAccountService;
import com.auto.service.GameItemOrderDetailService;
import com.auto.service.GameItemOrderService;
import com.auto.service.GameItemService;
import com.auto.service.GameRegionService;
import com.auto.service.GameService;
import com.auto.service.MachineGameAccountService;
import com.auto.service.MachineService;
import com.auto.service.TradeAssignmentService;
import com.auto.trade.statemachine.DeliveryEvent;
import com.auto.trade.statemachine.OrderDeliveryStateMachine;
import com.auto.ws.AgentRegistry;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.TransactionDefinition;
import org.springframework.transaction.TransactionStatus;
import org.springframework.transaction.support.SimpleTransactionStatus;

import java.util.List;
import java.util.Optional;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyList;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class TradeQueueCoordinatorTest {

    private GameItemOrderService orderService;
    private MachineGameAccountService machineGameService;
    private GameAccountService gameAccountService;
    private MachineService machineService;
    private TradeAssignmentService assignmentService;
    private AgentRegistry registry;
    private TradeMachineSelector selector;
    private OrderDeliveryStateMachine stateMachine;
    private GameService gameService;
    private ManualOrderStatusService manualOrderStatusService;
    private TradeDispatchCoordinator coordinator;

    @BeforeEach
    void setUp() {
        orderService = mock(GameItemOrderService.class);
        machineGameService = mock(MachineGameAccountService.class);
        gameAccountService = mock(GameAccountService.class);
        machineService = mock(MachineService.class);
        assignmentService = mock(TradeAssignmentService.class);
        registry = mock(AgentRegistry.class);
        selector = mock(TradeMachineSelector.class);
        stateMachine = mock(OrderDeliveryStateMachine.class);
        gameService = mock(GameService.class);
        manualOrderStatusService = mock(ManualOrderStatusService.class);
        coordinator = new TradeDispatchCoordinator(
                orderService, machineGameService, gameAccountService, machineService,
                assignmentService, registry, selector, stateMachine, gameService,
                mock(GameItemOrderDetailService.class), mock(GameItemService.class),
                mock(GameRegionService.class), manualOrderStatusService,
                mock(BuyerReviewAuditService.class),
                new ImmediateTransactionManager());
    }

    @Test
    void busyCompatibleMachineQueuesOrderInsteadOfReportingDispatchFailure() {
        GameItemOrder order = order("greeting");
        when(orderService.getById(42)).thenReturn(order);
        Game game = new Game();
        game.setTradeType("script");
        when(gameService.getById(3)).thenReturn(game);
        when(gameAccountService.findIdleByGameAndRegion(3, 5)).thenReturn(List.of());
        when(selector.select(eq(3), eq(5), anyList())).thenReturn(Optional.empty());

        GameAccount busyAccount = new GameAccount();
        busyAccount.setId(9);
        busyAccount.setGameId(3);
        busyAccount.setStatus("in_use");
        when(gameAccountService.findActiveByGameAndRegion(3, 5)).thenReturn(List.of(busyAccount));
        MachineGameAccount binding = new MachineGameAccount();
        binding.setMachineId(7);
        binding.setGameAccountId(9);
        binding.setPriority(10);
        when(machineGameService.findByGameAccountIdsActive(List.of(9))).thenReturn(List.of(binding));
        TradeAssignment active = new TradeAssignment();
        active.setMachineId(7);
        active.setGameAccountId(9);
        active.setStatus("trading");
        when(assignmentService.findByStatuses(any())).thenReturn(List.of(active));
        when(registry.isAgentGameExecutor(7)).thenReturn(true);
        when(registry.isAgentOnline(7)).thenReturn(true);
        when(orderService.count(any())).thenReturn(0L);

        assertNull(coordinator.dispatch(42));

        verify(stateMachine).fire(eq(order), eq(DeliveryEvent.QUEUE_ASSIGNMENT),
                org.mockito.ArgumentMatchers.argThat(context ->
                        Integer.valueOf(7).equals(context.get("machineId"))
                                && Integer.valueOf(9).equals(context.get("gameAccountId"))));
    }

    @Test
    void manualCancellationWaitsForWorkerTerminalAcknowledgement() throws Exception {
        GameItemOrder order = order("assigned");
        order.setAssignmentId("assignment-1");
        order.setAssignedMachineId(7);
        order.setGameAccountId(9);
        when(orderService.getById(42)).thenReturn(order);

        TradeAssignment assignment = new TradeAssignment();
        assignment.setAssignmentId("assignment-1");
        assignment.setMachineId(7);
        assignment.setGameAccountId(9);
        assignment.setStatus("trading");
        when(assignmentService.getOne(any(), eq(false))).thenReturn(assignment);
        CountDownLatch stopSent = new CountDownLatch(1);
        when(registry.sendTradeCancel(7, "assignment-1", "manual_cancel"))
                .thenAnswer(invocation -> {
                    stopSent.countDown();
                    return true;
                });
        GameItemOrder cancelled = order("cancelled");
        cancelled.setStatus("cancelled");
        when(manualOrderStatusService.cancelAfterAutomationStopped(42)).thenReturn(cancelled);

        ExecutorService executor = Executors.newSingleThreadExecutor();
        try {
            Future<GameItemOrder> resultFuture =
                    executor.submit(() -> coordinator.cancelOrderManually(42));
            assertTrue(stopSent.await(1, TimeUnit.SECONDS));
            verify(manualOrderStatusService, never()).cancelAfterAutomationStopped(42);

            coordinator.handleStatus(
                    "assignment-1", 7, "cancelled",
                    "trade execution stopped", "TRADE_CANCELLED");
            GameItemOrder result = resultFuture.get(1, TimeUnit.SECONDS);

            assertEquals("cancelled", result.getStatus());
            assertEquals("manually_cancelled", assignment.getStatus());
            verify(registry).sendTradeCancel(7, "assignment-1", "manual_cancel");
            verify(manualOrderStatusService).cancelAfterAutomationStopped(42);
        } finally {
            executor.shutdownNow();
        }
    }

    @Test
    void manualCancellationKeepsOrderActiveWhenStopCannotBeDelivered() {
        GameItemOrder order = order("assigned");
        order.setAssignmentId("assignment-1");
        order.setAssignedMachineId(7);
        order.setGameAccountId(9);
        when(orderService.getById(42)).thenReturn(order);

        TradeAssignment assignment = new TradeAssignment();
        assignment.setAssignmentId("assignment-1");
        assignment.setMachineId(7);
        assignment.setGameAccountId(9);
        assignment.setStatus("trading");
        when(assignmentService.getOne(any(), eq(false))).thenReturn(assignment);
        when(registry.sendTradeCancel(7, "assignment-1", "manual_cancel"))
                .thenReturn(false);

        IllegalStateException error = assertThrows(
                IllegalStateException.class,
                () -> coordinator.cancelOrderManually(42));

        assertEquals("停止指令未送达 Worker，订单状态保持不变", error.getMessage());
        verify(manualOrderStatusService, never()).cancelAfterAutomationStopped(42);
    }

    @Test
    void manualCancellationPreservesWorkerReportedCompletion() {
        GameItemOrder order = order("assigned");
        order.setAssignmentId("assignment-1");
        order.setAssignedMachineId(7);
        order.setGameAccountId(9);
        when(orderService.getById(42)).thenReturn(order);

        TradeAssignment assignment = new TradeAssignment();
        assignment.setAssignmentId("assignment-1");
        assignment.setOrderId(42);
        assignment.setMachineId(7);
        assignment.setGameAccountId(9);
        assignment.setStatus("trading");
        when(assignmentService.getOne(any(), eq(false))).thenReturn(assignment);
        when(registry.sendTradeCancel(7, "assignment-1", "manual_cancel"))
                .thenAnswer(invocation -> {
                    coordinator.handleStatus(
                            "assignment-1", 7, "completed",
                            "game trade completed", "");
                    return true;
                });

        IllegalStateException error = assertThrows(
                IllegalStateException.class,
                () -> coordinator.cancelOrderManually(42));

        assertEquals(
                "Worker 已确认游戏交易完成，不能取消订单，请标记为已完成",
                error.getMessage());
        verify(stateMachine).fire(
                eq(order),
                eq(DeliveryEvent.GAME_TRADE_COMPLETED),
                any());
        verify(manualOrderStatusService, never()).cancelAfterAutomationStopped(42);
    }

    private static GameItemOrder order(String deliveryStatus) {
        GameItemOrder order = new GameItemOrder();
        order.setId(42);
        order.setGameId(3);
        order.setRegionId(5);
        order.setDeliveryStatus(deliveryStatus);
        order.setStatus("pending");
        return order;
    }

    private static final class ImmediateTransactionManager implements PlatformTransactionManager {
        @Override
        public TransactionStatus getTransaction(TransactionDefinition definition) {
            return new SimpleTransactionStatus();
        }

        @Override
        public void commit(TransactionStatus status) {
        }

        @Override
        public void rollback(TransactionStatus status) {
            throw new AssertionError("测试事务不应回滚");
        }
    }
}
