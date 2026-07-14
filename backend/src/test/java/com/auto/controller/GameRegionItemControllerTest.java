package com.auto.controller;

import com.auto.common.ApiException;
import com.auto.entity.GameRegionItem;
import com.auto.service.GameRegionItemService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.IntStream;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.anyList;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class GameRegionItemControllerTest {

    private GameRegionItemService service;
    private GameRegionItemController controller;

    @BeforeEach
    void setUp() {
        service = mock(GameRegionItemService.class);
        controller = new GameRegionItemController(service);
    }

    @Test
    void batchUpdateRejectsEmptyPayloadBeforeDatabaseAccess() {
        assertThrows(ApiException.class, () -> controller.batchUpdate(payload()));
        verify(service, never()).listByIds(anyList());
        verify(service, never()).updateBatchById(anyList());
    }

    @Test
    void batchUpdateRejectsDuplicateIdAndNegativeStock() {
        Map<String, Object> payload = payload(item(1, 2), item(1, -1));

        assertThrows(ApiException.class, () -> controller.batchUpdate(payload));

        verify(service, never()).listByIds(anyList());
        verify(service, never()).updateBatchById(anyList());
    }

    @Test
    void batchUpdateRejectsMissingRecordsWithoutPartialSave() {
        Map<String, Object> payload = payload(item(1, 2), item(2, 3));
        when(service.listByIds(List.of(1, 2))).thenReturn(List.of(entity(1, 0)));

        assertThrows(ApiException.class, () -> controller.batchUpdate(payload));

        verify(service, never()).updateBatchById(anyList());
    }

    @Test
    void batchUpdateLoadsAndSavesOnceAfterCompleteValidation() {
        GameRegionItem first = entity(1, 0);
        GameRegionItem second = entity(2, 0);
        Map<String, Object> payload = payload(item(1, 5), item(2, 8));
        when(service.listByIds(List.of(1, 2))).thenReturn(List.of(second, first));

        List<GameRegionItem> result = controller.batchUpdate(payload);

        // 返回顺序沿用 listByIds 结果 [second(id2), first(id1)]，对应库存 [8, 5]
        assertEquals(List.of(8, 5), result.stream().map(GameRegionItem::getStock).toList());
        verify(service).listByIds(List.of(1, 2));
        verify(service).updateBatchById(anyList());
    }

    @Test
    void batchUpdateRejectsOversizedPayloadBeforeDatabaseAccess() {
        Map<String, Object> payload = payload(IntStream.rangeClosed(1, 501)
                .mapToObj(id -> item(id, 1))
                .toArray(Map[]::new));

        assertThrows(ApiException.class, () -> controller.batchUpdate(payload));

        verify(service, never()).listByIds(anyList());
        verify(service, never()).updateBatchById(anyList());
    }

    @SafeVarargs
    private Map<String, Object> payload(Map<String, Object>... items) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("items", List.of(items));
        return payload;
    }

    private Map<String, Object> item(Integer id, Integer stock) {
        Map<String, Object> item = new LinkedHashMap<>();
        item.put("id", id);
        item.put("stock", stock);
        return item;
    }

    private GameRegionItem entity(Integer id, Integer stock) {
        GameRegionItem entity = new GameRegionItem();
        entity.setId(id);
        entity.setStock(stock);
        return entity;
    }
}
