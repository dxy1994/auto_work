package com.auto.trade;

import com.auto.entity.GameAccount;
import com.auto.entity.GameItemOrder;
import com.auto.entity.MachineGame;
import com.auto.service.GameAccountService;
import com.auto.service.GameItemOrderService;
import com.auto.service.MachineGameService;
import com.auto.service.MachineService;
import com.auto.service.TradeAssignmentService;
import com.auto.service.TradeEventService;
import com.auto.ws.AgentRegistry;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class TradeDispatchCoordinatorTest {

    private GameItemOrderService orderService;
    private MachineGameService machineGameService;
    private GameAccountService gameAccountService;
    private MachineService machineService;
    private TradeAssignmentService assignmentService;
    private TradeEventService eventService;
    private AgentRegistry agentRegistry;
    private TradeDispatchCoordinator coordinator;

    @BeforeEach
    void setUp() {
        orderService = mock(GameItemOrderService.class);
        machineGameService = mock(MachineGameService.class);
        gameAccountService = mock(GameAccountService.class);
        machineService = mock(MachineService.class);
        assignmentService = mock(TradeAssignmentService.class);
        eventService = mock(TradeEventService.class);
        agentRegistry = mock(AgentRegistry.class);
        coordinator = new TradeDispatchCoordinator(
                orderService,
                machineGameService,
                gameAccountService,
                machineService,
                assignmentService,
                eventService,
                agentRegistry,
                new TradeMachineSelector());
        stubEligibleOrderAndMachine();
    }

    @Test
    void acceptedOfferMovesOrderToAssignedAndSendsStart() {
        TradeOffer offer = coordinator.dispatch(55);

        coordinator.handleDecision(offer.assignmentId(), 1, true, null);

        verify(agentRegistry).sendTradeStart(
                offer.machineId(), offer.assignmentId(), offer.executionToken());
        verify(orderService).updateDeliveryStatus(
                55, "offered", "assigned", offer.assignmentId());
    }

    @Test
    void rejectedOfferReturnsOrderToWaitingAssignment() {
        TradeOffer offer = coordinator.dispatch(55);

        coordinator.handleDecision(offer.assignmentId(), 1, false, "ui_not_ready");

        verify(orderService).updateDeliveryStatus(
                55, "offered", "waiting_assignment", null);
        verify(agentRegistry, never()).sendTradeStart(anyInt(), anyString(), anyString());
    }

    @Test
    void staleDecisionCannotStartTrade() {
        assertThatThrownBy(() -> coordinator.handleDecision("unknown", 1, true, null))
                .isInstanceOf(IllegalStateException.class);

        verify(agentRegistry, never()).sendTradeStart(anyInt(), anyString(), anyString());
    }

    @Test
    void decisionFromDifferentMachineCannotStartTrade() {
        TradeOffer offer = coordinator.dispatch(55);

        assertThatThrownBy(() -> coordinator.handleDecision(
                offer.assignmentId(), 99, true, null))
                .isInstanceOf(IllegalStateException.class);

        verify(agentRegistry, never()).sendTradeStart(anyInt(), anyString(), anyString());
    }

    @Test
    void runtimeForDifferentGameCannotReceiveOffer() {
        when(agentRegistry.getRuntimeStatus(1)).thenReturn(new WorkerRuntimeStatus(
                88, 101, 4, "logged_in", "seller", "idle", null, "ready"));

        assertThatThrownBy(() -> coordinator.dispatch(55))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("没有符合条件");

        verify(agentRegistry, never()).sendTradeOffer(anyInt(), any(TradeOffer.class));
    }

    @Test
    void expiredOfferReturnsOrderAndResourcesToIdlePool() {
        TradeOffer offer = coordinator.dispatch(55);

        coordinator.expireOffersAt(offer.leaseExpiresAt().plusSeconds(1));

        verify(orderService).updateDeliveryStatus(
                55, "offered", "waiting_assignment", null);
        verify(agentRegistry, never()).sendTradeStart(anyInt(), anyString(), anyString());
    }

    private void stubEligibleOrderAndMachine() {
        GameItemOrder order = new GameItemOrder();
        order.setId(55);
        order.setGameId(9);
        order.setRegionId(4);
        order.setDeliveryStatus("waiting_assignment");
        order.setAssetType("adena");
        when(orderService.getById(55)).thenReturn(order);

        MachineGame machineGame = new MachineGame();
        machineGame.setMachineId(1);
        machineGame.setGameId(9);
        machineGame.setPriority(20);
        machineGame.setIsActive(1);
        when(machineGameService.findByGameIdActiveOrderByPriorityDesc(9))
                .thenReturn(List.of(machineGame));

        GameAccount account = new GameAccount();
        account.setId(101);
        account.setMachineId(1);
        account.setGameId(9);
        account.setRegionId(4);
        account.setStatus("idle");
        account.setIsActive(1);
        when(gameAccountService.findIdleByGameAndRegion(9, 4))
                .thenReturn(List.of(account));

        when(agentRegistry.isAgentOnline(1)).thenReturn(true);
        when(agentRegistry.getRuntimeStatus(1)).thenReturn(new WorkerRuntimeStatus(
                9, 101, 4, "logged_in", "seller", "idle", null, "ready"));
        when(agentRegistry.sendTradeOffer(anyInt(), any(TradeOffer.class))).thenReturn(true);
        when(agentRegistry.sendTradeStart(anyInt(), anyString(), anyString())).thenReturn(true);
    }
}
