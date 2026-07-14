package com.auto.controller;

import com.auto.common.ApiException;
import com.auto.entity.GameItem;
import com.auto.entity.GameRegion;
import com.auto.service.GameItemOrderDetailService;
import com.auto.service.GameItemOrderService;
import com.auto.service.GameItemService;
import com.auto.service.GameRegionService;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

class OrderControllerConsistencyTest {

    private GameItemOrderService orderService;
    private GameItemService itemService;
    private GameRegionService regionService;
    private OrderController controller;

    @BeforeEach
    void setUp() {
        orderService = mock(GameItemOrderService.class);
        itemService = mock(GameItemService.class);
        regionService = mock(GameRegionService.class);
        controller = new OrderController(orderService, mock(GameItemOrderDetailService.class),
                itemService, regionService, new ObjectMapper());
    }

    @Test
    void createRejectsRegionOwnedByAnotherGameBeforeSavingOrder() {
        GameRegion region = new GameRegion();
        region.setId(10);
        region.setGameId(2);
        when(regionService.getById(10)).thenReturn(region);

        assertThrows(ApiException.class, () -> controller.create(payload(1, 10, 20)));

        verifyNoInteractions(orderService);
    }

    @Test
    void createRejectsItemOwnedByAnotherGameBeforeSavingOrder() {
        GameRegion region = new GameRegion();
        region.setId(10);
        region.setGameId(1);
        GameItem item = new GameItem();
        item.setId(20);
        item.setGameId(2);
        when(regionService.getById(10)).thenReturn(region);
        when(itemService.listByIds(List.of(20))).thenReturn(List.of(item));

        assertThrows(ApiException.class, () -> controller.create(payload(1, 10, 20)));

        verifyNoInteractions(orderService);
    }

    private OrderController.OrderCreate payload(int gameId, int regionId, int itemId) {
        OrderController.OrderDetailCreate detail = new OrderController.OrderDetailCreate();
        detail.itemId = itemId;
        OrderController.OrderCreate payload = new OrderController.OrderCreate();
        payload.gameId = gameId;
        payload.regionId = regionId;
        payload.details = List.of(detail);
        return payload;
    }
}
