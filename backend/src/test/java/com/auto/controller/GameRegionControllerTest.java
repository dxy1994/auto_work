package com.auto.controller;

import com.auto.common.ApiException;
import com.auto.entity.GameRegion;
import com.auto.service.GameItemService;
import com.auto.service.GameRegionInventoryService;
import com.auto.service.GameRegionInventoryShopPriceService;
import com.auto.service.GameRegionService;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class GameRegionControllerTest {

    @Test
    void acceptsBottomRightCoordinateOf1280x960Client() {
        GameRegionService regionService = mock(GameRegionService.class);
        GameItemService itemService = mock(GameItemService.class);
        GameRegionInventoryService inventoryService = mock(GameRegionInventoryService.class);
        GameRegionController controller = new GameRegionController(
                regionService,
                itemService,
                inventoryService,
                mock(GameRegionInventoryShopPriceService.class));
        GameRegion payload = region(1279, 959);
        when(itemService.findByGameIdActive(1)).thenReturn(List.of());
        when(inventoryService.findByRegionId(null)).thenReturn(List.of());

        assertDoesNotThrow(() -> controller.create(payload));

        verify(regionService).save(payload);
    }

    @Test
    void rejectsCoordinateOutside1280x960Client() {
        GameRegionController controller = new GameRegionController(
                mock(GameRegionService.class),
                mock(GameItemService.class),
                mock(GameRegionInventoryService.class),
                mock(GameRegionInventoryShopPriceService.class));

        assertThrows(ApiException.class, () -> controller.create(region(1280, 959)));
        assertThrows(ApiException.class, () -> controller.create(region(1279, 960)));
    }

    private static GameRegion region(int x, int y) {
        GameRegion region = new GameRegion();
        region.setGameId(1);
        region.setName("test");
        region.setCode("test");
        region.setSelectPage(1);
        region.setSelectX(x);
        region.setSelectY(y);
        return region;
    }
}
