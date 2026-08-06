package com.auto.trade;

import com.auto.entity.GameRegionInventory;
import com.auto.entity.PlatformSalesProduct;
import com.auto.service.GameRegionInventoryService;
import com.auto.service.InventoryChangeLogService;
import com.auto.service.PlatformSalesProductService;
import com.auto.service.SystemAlertService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class MarketplaceInventoryReconciliationServiceTest {

    private PlatformSalesProductService productService;
    private GameRegionInventoryService inventoryService;
    private InventoryChangeLogService changeLogService;
    private SystemAlertService alertService;
    private MarketplaceInventoryReconciliationService service;

    @BeforeEach
    void setUp() {
        productService = mock(PlatformSalesProductService.class);
        inventoryService = mock(GameRegionInventoryService.class);
        changeLogService = mock(InventoryChangeLogService.class);
        alertService = mock(SystemAlertService.class);
        service = new MarketplaceInventoryReconciliationService(
                productService,
                inventoryService,
                changeLogService,
                alertService);
    }

    @Test
    void enrichesMatchedProductWithMaximumAndMismatchStatus() {
        PlatformSalesProduct product = resolvedProduct("최소 1 최대 43");
        GameRegionInventory inventory = inventory(7L);
        when(inventoryService.findByRegionIdAndItemId(5, 7))
                .thenReturn(inventory);

        service.enrich(List.of(product));

        assertEquals(43L, product.getParsedQuantity());
        assertEquals(7L, product.getInventoryStock());
        assertEquals(91, product.getInventoryId());
        assertEquals("mismatch", product.getInventoryComparisonStatus());
    }

    @Test
    void snapshotMismatchNotificationIsTemporarilyDisabled() {
        PlatformSalesProduct product = resolvedProduct("1~43");
        when(inventoryService.findByRegionIdAndItemId(5, 7))
                .thenReturn(inventory(12L));

        service.reconcileSnapshotProduct(product);

        verify(alertService).dismissBySourceKey(
                "sales-product:11:39182563:inventory");
        verify(alertService, never()).openOrRefresh(
                any(), any(), any(), any(), any(), any(), any());
    }

    @Test
    void manualSyncOverwritesSystemInventoryAndClosesAlert() {
        PlatformSalesProduct product = resolvedProduct("10~43");
        product.setId(81);
        GameRegionInventory inventory = inventory(12L);
        when(productService.getById(81)).thenReturn(product);
        when(inventoryService.findByRegionIdAndItemId(5, 7))
                .thenReturn(inventory);

        PlatformSalesProduct result = service.syncInventoryFromPlatform(81);

        assertEquals(43L, inventory.getStock());
        assertEquals("matched", result.getInventoryComparisonStatus());
        verify(inventoryService).updateById(inventory);
        verify(changeLogService).logSystemSync(
                eq(inventory), eq(12L),
                org.mockito.ArgumentMatchers.contains("39182563"),
                eq("admin"));
        verify(alertService).dismissBySourceKey(
                "sales-product:11:39182563:inventory");
    }

    private static PlatformSalesProduct resolvedProduct(String quantity) {
        PlatformSalesProduct product = new PlatformSalesProduct();
        product.setPlatformAccountId(11);
        product.setPlatformProductId("39182563");
        product.setParseStatus("matched");
        product.setRegionId(5);
        product.setGameItemId(7);
        product.setRegionName("월드 거래소(마족)");
        product.setParsedItemName("키나");
        product.setQuantityText(quantity);
        return product;
    }

    private static GameRegionInventory inventory(long stock) {
        GameRegionInventory inventory = new GameRegionInventory();
        inventory.setId(91);
        inventory.setGameId(3);
        inventory.setRegionId(5);
        inventory.setItemId(7);
        inventory.setIsActive(1);
        inventory.setStock(stock);
        return inventory;
    }
}
