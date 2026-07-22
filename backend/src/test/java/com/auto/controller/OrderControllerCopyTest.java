package com.auto.controller;

import com.auto.entity.GameItem;
import com.auto.entity.GameItemOrder;
import com.auto.entity.GameItemOrderDetail;
import com.auto.entity.GameRegion;
import com.auto.entity.TradeEvent;
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
import org.springframework.context.ApplicationEventPublisher;
import tools.jackson.databind.ObjectMapper;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyCollection;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class OrderControllerCopyTest {

    @Test
    @SuppressWarnings({"unchecked", "rawtypes"})
    void copiesBusinessDataWithNewNumbersAndResetsToAfterGreeting() {
        GameItemOrderService orderService = mock(GameItemOrderService.class);
        GameItemOrderDetailService detailService = mock(GameItemOrderDetailService.class);
        GameItemService itemService = mock(GameItemService.class);
        GameRegionService regionService = mock(GameRegionService.class);
        GameRegionInventoryService inventoryService = mock(GameRegionInventoryService.class);
        TradeAssignmentService assignmentService = mock(TradeAssignmentService.class);
        TradeEventService eventService = mock(TradeEventService.class);
        ObjectMapper objectMapper = mock(ObjectMapper.class);

        OrderController controller = new OrderController(
                orderService,
                detailService,
                itemService,
                regionService,
                inventoryService,
                mock(GameRegionInventoryShopPriceService.class),
                mock(ApplicationEventPublisher.class),
                mock(PlatformAccountService.class),
                mock(MachinePlatformAccountService.class),
                mock(PlatformService.class),
                mock(AgentRegistry.class),
                objectMapper,
                mock(OrderDeliveryStateMachine.class),
                assignmentService,
                mock(TradeDispatchCoordinator.class),
                mock(OrderRecoveryService.class),
                mock(GreetingDispatchService.class),
                mock(ManualOrderStatusService.class),
                eventService);

        GameItemOrder source = new GameItemOrder();
        source.setId(7);
        source.setOrderNo("ORDER-7");
        source.setSourceOrderNo("PLATFORM-7");
        source.setDeliveryStatus("assigned");
        source.setStatus("pending");
        source.setAssignmentId("assignment-old");
        source.setLastErrorCode("OLD_ERROR");
        when(orderService.getById(7)).thenReturn(source);

        GameRegion region = new GameRegion();
        region.setId(11);
        region.setGameId(3);
        when(regionService.getById(11)).thenReturn(region);

        GameItem item = new GameItem();
        item.setId(21);
        item.setGameId(3);
        item.setName("测试物品");
        item.setPrice(new BigDecimal("10.00"));
        when(itemService.listByIds(anyCollection())).thenReturn(List.of(item));

        List<GameItemOrderDetail> copiedDetails = new ArrayList<>();
        when(orderService.save(any(GameItemOrder.class))).thenAnswer(invocation -> {
            GameItemOrder saved = invocation.getArgument(0);
            saved.setId(99);
            return true;
        });
        when(detailService.save(any(GameItemOrderDetail.class))).thenAnswer(invocation -> {
            copiedDetails.add(invocation.getArgument(0));
            return true;
        });
        when(detailService.sumSubtotalByOrderId(99)).thenReturn(new BigDecimal("20.00"));
        when(detailService.findByOrderId(99)).thenAnswer(ignored -> copiedDetails);
        when(objectMapper.convertValue(any(GameItemOrder.class), eq(Map.class)))
                .thenAnswer(invocation -> new LinkedHashMap<>());

        OrderController.OrderDetailCopy detail = new OrderController.OrderDetailCopy();
        detail.itemId = 21;
        detail.quantity = 2;
        detail.unitPrice = new BigDecimal("10.00");
        detail.remark = "可修改的明细备注";

        OrderController.OrderCopy payload = new OrderController.OrderCopy();
        payload.websiteId = 1;
        payload.gameId = 3;
        payload.regionId = 11;
        payload.deliveryStatus = "waiting_assignment";
        payload.status = "pending";
        payload.productTitle = "复制后的商品标题";
        payload.customerName = "新客户";
        payload.details = List.of(detail);

        controller.copy(7, payload);

        assertNotEquals(source.getOrderNo(), payload.orderNo);
        assertTrue(payload.orderNo.contains("-COPY-"));
        assertNotEquals(source.getSourceOrderNo(), payload.sourceOrderNo);
        assertTrue(payload.sourceOrderNo.contains("-COPY-"));

        // convertValue 在此测试中被 mock；从 save 参数验证新订单的实际持久化内容。
        org.mockito.ArgumentCaptor<GameItemOrder> orderCaptor =
                org.mockito.ArgumentCaptor.forClass(GameItemOrder.class);
        verify(orderService).save(orderCaptor.capture());
        GameItemOrder copied = orderCaptor.getValue();
        assertEquals("waiting_assignment", copied.getDeliveryStatus());
        assertEquals("pending", copied.getStatus());
        assertEquals("复制后的商品标题", copied.getProductTitle());
        assertEquals("新客户", copied.getCustomerName());
        assertNull(copied.getAssignmentId());
        assertNull(copied.getLastErrorCode());

        assertEquals(1, copiedDetails.size());
        assertEquals("pending", copiedDetails.get(0).getStatus());
        assertEquals(new BigDecimal("20.00"), copiedDetails.get(0).getSubtotal());
        assertEquals("可修改的明细备注", copiedDetails.get(0).getRemark());
        verify(eventService).save(any(TradeEvent.class));
    }
}
