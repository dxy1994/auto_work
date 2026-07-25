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

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyList;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
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
    void manualCancellationStopsRunningWorkerBeforeCancellingOrder() {
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
        when(registry.sendTradeCancel(7, "assignment-1", "manual_cancel")).thenReturn(true);
        GameItemOrder cancelled = order("cancelled");
        cancelled.setStatus("cancelled");
        when(manualOrderStatusService.cancelAfterAutomationStopped(42)).thenReturn(cancelled);

        GameItemOrder result = coordinator.cancelOrderManually(42);

        assertEquals("cancelled", result.getStatus());
        assertEquals("manually_cancelled", assignment.getStatus());
        verify(registry).sendTradeCancel(7, "assignment-1", "manual_cancel");
        verify(manualOrderStatusService).cancelAfterAutomationStopped(42);
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
