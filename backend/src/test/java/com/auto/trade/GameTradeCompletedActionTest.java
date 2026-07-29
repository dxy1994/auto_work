package com.auto.trade;

import com.auto.entity.GameItemOrder;
import com.auto.service.GameAccountService;
import com.auto.service.MachineService;
import com.auto.service.TradeAssignmentService;
import com.auto.trade.statemachine.DeliveryState;
import com.auto.trade.statemachine.actions.GameTradeCompletedAction;
import com.auto.ws.AgentRegistry;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.mockito.InOrder;
import org.springframework.context.ApplicationEventPublisher;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.inOrder;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class GameTradeCompletedActionTest {

    @Test
    void publishesWebsiteConfirmationOnlyAfterGameDeliveryIsRecorded() {
        TradeAssignmentService assignmentService = mock(TradeAssignmentService.class);
        MachineService machineService = mock(MachineService.class);
        GameAccountService gameAccountService = mock(GameAccountService.class);
        AgentRegistry agentRegistry = mock(AgentRegistry.class);
        TradeCompletionService completionService = mock(TradeCompletionService.class);
        ApplicationEventPublisher publisher = mock(ApplicationEventPublisher.class);
        when(assignmentService.getOne(any(), eq(false))).thenReturn(null);
        GameTradeCompletedAction action = new GameTradeCompletedAction(
                assignmentService,
                machineService,
                gameAccountService,
                agentRegistry,
                completionService,
                publisher);
        GameItemOrder gameOrder = new GameItemOrder();
        gameOrder.setId(42);

        action.execute(
                gameOrder,
                DeliveryState.ASSIGNED,
                DeliveryState.WAIT_WEB_CONFIRM,
                Map.of(
                        "assignmentId", "assignment-1",
                        "machineId", 7,
                        "gameAccountId", 9));

        ArgumentCaptor<GameDeliveryConfirmationRequested> event =
                ArgumentCaptor.forClass(GameDeliveryConfirmationRequested.class);
        InOrder calls = inOrder(completionService, publisher);
        calls.verify(completionService).gameDelivered(gameOrder);
        calls.verify(publisher).publishEvent(event.capture());
        assertEquals(42, event.getValue().orderId());
    }
}
