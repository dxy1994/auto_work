package com.auto.trade;

import com.auto.entity.GameItem;
import com.auto.entity.GameItemOrder;
import com.auto.entity.GameItemOrderDetail;
import com.auto.service.GameItemOrderDetailService;
import com.auto.service.GameItemOrderService;
import com.auto.service.GameItemService;
import com.auto.service.GameRegionInventoryService;
import com.auto.service.ItemBundleRelationService;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.math.BigDecimal;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class OrderDetailGenerationServiceTest {

    @Mock
    private GameItemService gameItemService;
    @Mock
    private ItemBundleRelationService bundleItemService;
    @Mock
    private GameItemOrderDetailService detailService;
    @Mock
    private GameItemOrderService orderService;
    @Mock
    private GameRegionInventoryService regionInventoryService;

    @InjectMocks
    private OrderDetailGenerationService generationService;

    @Test
    void retryGeneratesMissingDetailUsingCodeFirstMatcher() {
        GameItemOrder order = new GameItemOrder();
        order.setId(42);
        order.setGameId(7);
        order.setRegionId(null);
        order.setTradeItemName("ADENA");

        GameItem item = new GameItem();
        item.setId(9);
        item.setName("金币");
        item.setIsBundle(0);
        item.setPrice(new BigDecimal("12.50"));

        when(orderService.getOne(any(), eq(false))).thenReturn(order);
        when(detailService.findByOrderId(42)).thenReturn(List.of());
        when(gameItemService.findActiveByGameIdAndCodeOrName(7, "ADENA")).thenReturn(item);

        List<GameItemOrderDetail> result = generationService.ensureDetails(order);

        assertEquals(1, result.size());
        assertEquals(new BigDecimal("12.50"), order.getTotalAmount());
        ArgumentCaptor<GameItemOrderDetail> saved = ArgumentCaptor.forClass(GameItemOrderDetail.class);
        verify(detailService).save(saved.capture());
        assertEquals(42, saved.getValue().getOrderId());
        assertEquals(9, saved.getValue().getItemId());
        assertEquals("金币", saved.getValue().getItemName());
        verify(orderService).updateById(order);
    }

    @Test
    void retryDoesNotDuplicateExistingDetails() {
        GameItemOrder order = new GameItemOrder();
        order.setId(42);
        GameItemOrderDetail existing = new GameItemOrderDetail();
        existing.setId(100);

        when(orderService.getOne(any(), eq(false))).thenReturn(order);
        when(detailService.findByOrderId(42)).thenReturn(List.of(existing));

        List<GameItemOrderDetail> result = generationService.ensureDetails(order);

        assertEquals(1, result.size());
        assertSame(existing, result.get(0));
        verify(gameItemService, never()).findActiveByGameIdAndCodeOrName(any(), any());
        verify(detailService, never()).save(any());
        verify(orderService, never()).updateById(any());
    }
}
