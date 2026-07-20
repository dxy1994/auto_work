package com.auto.trade;

import com.auto.entity.GameItemOrder;
import com.auto.entity.GameItemOrderDetail;
import com.auto.entity.GameRegionInventory;
import com.auto.service.GameItemOrderDetailService;
import com.auto.service.GameRegionInventoryService;
import com.auto.service.InventoryChangeLogService;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class TradeCompletionServiceTest {

    @Test
    void completionMarksDetailsAndDeductsInventory() {
        GameItemOrderDetailService detailService = mock(GameItemOrderDetailService.class);
        GameRegionInventoryService inventoryService = mock(GameRegionInventoryService.class);
        InventoryChangeLogService changeLogService = mock(InventoryChangeLogService.class);
        TradeCompletionService service = new TradeCompletionService(
                detailService, inventoryService, changeLogService);

        GameItemOrder order = new GameItemOrder();
        order.setId(42);
        order.setRegionId(3);

        GameItemOrderDetail detail = new GameItemOrderDetail();
        detail.setId(5);
        detail.setOrderId(42);
        detail.setItemId(8);
        detail.setQuantity(3);

        GameRegionInventory inventory = new GameRegionInventory();
        inventory.setId(11);
        inventory.setRegionId(3);
        inventory.setItemId(8);
        inventory.setStock(10);

        when(detailService.findByOrderId(42)).thenReturn(List.of(detail));
        when(inventoryService.findByRegionIdAndItemId(3, 8)).thenReturn(inventory);

        service.complete(order);

        assertEquals("completed", detail.getStatus());
        assertEquals(7, inventory.getStock());
        assertNotNull(order.getCompletedAt());
        assertNotNull(order.getGameDeliveredAt());
        assertNull(order.getLastErrorCode());
        verify(detailService).updateById(detail);
        verify(inventoryService).updateById(inventory);
        verify(changeLogService).logStockOut(
                inventory, 3, "auto_trade:order=42", "system");
    }
}
