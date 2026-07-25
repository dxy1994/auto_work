package com.auto.trade;

import com.auto.entity.Game;
import com.auto.entity.GameAccount;
import com.auto.entity.GameItemOrder;
import com.auto.entity.MachineGameAccount;
import com.auto.service.GameAccountService;
import com.auto.service.GameItemOrderDetailService;
import com.auto.service.GameItemOrderService;
import com.auto.service.GameItemService;
import com.auto.service.GameRegionService;
import com.auto.service.GameService;
import com.auto.service.MachineGameAccountService;
import com.auto.service.MachineService;
import com.auto.service.TradeAssignmentService;
import com.auto.trade.statemachine.OrderDeliveryStateMachine;
import com.auto.ws.AgentRegistry;
import org.junit.jupiter.api.Test;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.TransactionDefinition;
import org.springframework.transaction.TransactionStatus;
import org.springframework.transaction.support.SimpleTransactionStatus;

import java.util.List;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyList;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class TradeDispatchCoordinatorTransactionTest {

    @Test
    void commitsEachStateBeforeSendingTheCorrespondingWorkerCommand() {
        GameItemOrderService orderService = mock(GameItemOrderService.class);
        MachineGameAccountService machineGameService = mock(MachineGameAccountService.class);
        GameAccountService gameAccountService = mock(GameAccountService.class);
        MachineService machineService = mock(MachineService.class);
        TradeAssignmentService assignmentService = mock(TradeAssignmentService.class);
        AgentRegistry registry = mock(AgentRegistry.class);
        TradeMachineSelector selector = mock(TradeMachineSelector.class);
        OrderDeliveryStateMachine stateMachine = mock(OrderDeliveryStateMachine.class);
        GameService gameService = mock(GameService.class);
        GameItemOrderDetailService detailService = mock(GameItemOrderDetailService.class);
        GameItemService itemService = mock(GameItemService.class);
        GameRegionService regionService = mock(GameRegionService.class);
        ManualOrderStatusService manualOrderStatusService = mock(ManualOrderStatusService.class);
        RecordingTransactionManager transactionManager = new RecordingTransactionManager();

        GameItemOrder order = new GameItemOrder();
        order.setId(24);
        order.setGameId(3);
        order.setRegionId(5);
        order.setDeliveryStatus("greeting");
        order.setStatus("pending");
        when(orderService.getById(24)).thenReturn(order);

        Game game = new Game();
        game.setId(3);
        game.setTradeType("script");
        game.setTradeTimeoutSeconds(300);
        when(gameService.getById(3)).thenReturn(game);

        GameAccount account = new GameAccount();
        account.setId(9);
        account.setGameId(3);
        account.setStatus("idle");
        when(gameAccountService.findIdleByGameAndRegion(3, 5)).thenReturn(List.of(account));
        when(gameAccountService.getById(9)).thenReturn(account);

        MachineGameAccount binding = new MachineGameAccount();
        binding.setMachineId(1);
        binding.setGameAccountId(9);
        binding.setPriority(10);
        when(machineGameService.findByGameAccountIdsActive(anyList())).thenReturn(List.of(binding));
        when(registry.isAgentGameExecutor(1)).thenReturn(true);
        when(registry.isAgentOnline(1)).thenReturn(true);

        TradeCandidate candidate = new TradeCandidate(
                1, 9, 3, 5, 10, true, true, true,
                "logged_in", "idle", "ready", null);
        when(selector.select(eq(3), eq(5), anyList())).thenReturn(Optional.of(candidate));
        when(detailService.findByOrderId(24)).thenReturn(List.of());

        when(registry.sendTradeOffer(eq(1), any())).thenAnswer(invocation -> {
            assertEquals(1, transactionManager.commitCount,
                    "OFFERED 必须在发送 offer 前提交");
            return true;
        });
        when(registry.sendTradeStart(eq(1), any(), any())).thenAnswer(invocation -> {
            assertEquals(2, transactionManager.commitCount,
                    "ASSIGNED 必须在发送 trade_start 前提交");
            return true;
        });

        TradeDispatchCoordinator coordinator = new TradeDispatchCoordinator(
                orderService, machineGameService, gameAccountService, machineService,
                assignmentService, registry, selector, stateMachine, gameService,
                detailService, itemService, regionService, manualOrderStatusService,
                mock(BuyerReviewAuditService.class),
                transactionManager);

        TradeOffer offer = coordinator.dispatch(24);
        // 本测试使用 mock 状态机，手动反映真实状态机会持久化的 OFFERED 状态。
        order.setDeliveryStatus("offered");
        coordinator.handleDecision(offer.assignmentId(), 1, true, null);

        assertTrue(offer.leaseExpiresAt().isAfter(java.time.Instant.now()));
        verify(registry).sendTradeOffer(1, offer);
        verify(registry).sendTradeStart(1, offer.assignmentId(), offer.executionToken());
    }

    private static final class RecordingTransactionManager implements PlatformTransactionManager {
        private int commitCount;

        @Override
        public TransactionStatus getTransaction(TransactionDefinition definition) {
            return new SimpleTransactionStatus();
        }

        @Override
        public void commit(TransactionStatus status) {
            commitCount++;
        }

        @Override
        public void rollback(TransactionStatus status) {
            throw new AssertionError("测试流程不应回滚");
        }
    }
}
