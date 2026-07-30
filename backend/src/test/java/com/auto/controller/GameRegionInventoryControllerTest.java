package com.auto.controller;

import com.auto.common.ApiException;
import com.auto.entity.GameRegionInventory;
import com.auto.service.GameRegionInventoryService;
import com.auto.service.GameRegionInventoryShopPriceService;
import com.auto.service.InventoryChangeLogService;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class GameRegionInventoryControllerTest {

    @Test
    void stockInSupportsQuantityBeyondIntegerRange() {
        GameRegionInventoryService inventoryService = mock(GameRegionInventoryService.class);
        InventoryChangeLogService logService = mock(InventoryChangeLogService.class);
        GameRegionInventoryController controller = new GameRegionInventoryController(
                inventoryService,
                mock(GameRegionInventoryShopPriceService.class),
                logService);
        GameRegionInventory inventory = inventory(3_000_000_000L);
        when(inventoryService.getById(11)).thenReturn(inventory);

        Map<String, Object> response = controller.stockIn(Map.of(
                "inventory_id", 11,
                "quantity", 2_000_000_000L,
                "unit_price", "3.00"));

        assertEquals(5_000_000_000L, response.get("stock"));
        assertEquals(5_000_000_000L, inventory.getStock());
        assertEquals(new BigDecimal("2.4000"), inventory.getPurchasePrice());
        verify(inventoryService).updateById(inventory);
        verify(logService).logStockIn(
                inventory,
                2_000_000_000L,
                new BigDecimal("3.00"),
                new BigDecimal("2.00"),
                new BigDecimal("2.4000"),
                "admin");
    }

    @Test
    void stockInRejectsLongOverflow() {
        GameRegionInventoryService inventoryService = mock(GameRegionInventoryService.class);
        GameRegionInventoryController controller = new GameRegionInventoryController(
                inventoryService,
                mock(GameRegionInventoryShopPriceService.class),
                mock(InventoryChangeLogService.class));
        when(inventoryService.getById(11)).thenReturn(inventory(Long.MAX_VALUE));

        ApiException error = assertThrows(
                ApiException.class,
                () -> controller.stockIn(Map.of(
                        "inventory_id", 11,
                        "quantity", 1L,
                        "unit_price", "1.00")));

        assertEquals("入库后库存数量超出 long 类型范围", error.getMessage());
    }

    private static GameRegionInventory inventory(long stock) {
        GameRegionInventory inventory = new GameRegionInventory();
        inventory.setId(11);
        inventory.setGameId(1);
        inventory.setRegionId(2);
        inventory.setItemId(3);
        inventory.setStock(stock);
        inventory.setPurchasePrice(new BigDecimal("2.00"));
        return inventory;
    }
}
