package com.auto.controller;

import com.auto.common.ApiException;
import com.auto.entity.GameItemOrder;
import com.auto.service.GameItemOrderDetailService;
import com.auto.service.GameItemOrderService;
import com.auto.service.GameItemService;
import com.auto.service.GameRegionInventoryService;
import com.auto.service.GameRegionInventoryShopPriceService;
import com.auto.service.GameRegionService;
import com.auto.service.MachinePlatformAccountService;
import com.auto.service.PlatformAccountService;
import com.auto.service.PlatformService;
import com.auto.service.TradeAssignmentService;
import com.auto.service.TradeEventService;
import com.auto.trade.GreetingDispatchService;
import com.auto.trade.ManualOrderStatusService;
import com.auto.trade.OrderRecoveryService;
import com.auto.trade.TradeDispatchCoordinator;
import com.auto.trade.statemachine.OrderDeliveryStateMachine;
import com.auto.ws.AgentRegistry;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.springframework.context.ApplicationEventPublisher;
import tools.jackson.databind.ObjectMapper;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class OrderControllerDeleteTest {

    @ParameterizedTest
    @CsvSource({
            "pending,queued",
            "assigned,assigned",
            "processing,executing",
            "cancelled,cancelled",
            "abnormal,review_required"
    })
    void deletesEveryNonCompletedOrder(String status, String deliveryStatus) {
        GameItemOrderService orderService = mock(GameItemOrderService.class);
        GameItemOrderDetailService detailService = mock(GameItemOrderDetailService.class);
        OrderController controller = controller(orderService, detailService);
        GameItemOrder order = order(status, deliveryStatus);
        when(orderService.getById(42)).thenReturn(order);
        when(detailService.findByOrderId(42)).thenReturn(List.of());

        controller.delete(42);

        verify(orderService).removeById(42);
    }

    @Test
    void rejectsCompletedOrderDeletion() {
        GameItemOrderService orderService = mock(GameItemOrderService.class);
        GameItemOrderDetailService detailService = mock(GameItemOrderDetailService.class);
        OrderController controller = controller(orderService, detailService);
        when(orderService.getById(42)).thenReturn(order("completed", "completed"));

        ApiException error = assertThrows(ApiException.class, () -> controller.delete(42));

        assertEquals("已完成订单不能删除", error.getMessage());
        verify(orderService, never()).removeById(42);
    }

    @Test
    void stopsActiveAutomationBeforeDeletingOrder() {
        GameItemOrderService orderService = mock(GameItemOrderService.class);
        GameItemOrderDetailService detailService = mock(GameItemOrderDetailService.class);
        TradeDispatchCoordinator coordinator = mock(TradeDispatchCoordinator.class);
        OrderController controller = controller(orderService, detailService, coordinator);
        when(orderService.getById(42)).thenReturn(order("processing", "assigned"));
        when(detailService.findByOrderId(42)).thenReturn(List.of());

        controller.delete(42);

        verify(coordinator).cancelOrderManually(42);
        verify(orderService).removeById(42);
    }

    private static GameItemOrder order(String status, String deliveryStatus) {
        GameItemOrder order = new GameItemOrder();
        order.setId(42);
        order.setStatus(status);
        order.setDeliveryStatus(deliveryStatus);
        return order;
    }

    private static OrderController controller(
            GameItemOrderService orderService,
            GameItemOrderDetailService detailService) {
        return controller(
                orderService,
                detailService,
                mock(TradeDispatchCoordinator.class));
    }

    private static OrderController controller(
            GameItemOrderService orderService,
            GameItemOrderDetailService detailService,
            TradeDispatchCoordinator tradeCoordinator) {
        return new OrderController(
                orderService,
                detailService,
                mock(GameItemService.class),
                mock(GameRegionService.class),
                mock(GameRegionInventoryService.class),
                mock(GameRegionInventoryShopPriceService.class),
                mock(ApplicationEventPublisher.class),
                mock(PlatformAccountService.class),
                mock(MachinePlatformAccountService.class),
                mock(PlatformService.class),
                mock(AgentRegistry.class),
                mock(ObjectMapper.class),
                mock(OrderDeliveryStateMachine.class),
                mock(TradeAssignmentService.class),
                tradeCoordinator,
                mock(OrderRecoveryService.class),
                mock(GreetingDispatchService.class),
                mock(ManualOrderStatusService.class),
                mock(TradeEventService.class));
    }
}
