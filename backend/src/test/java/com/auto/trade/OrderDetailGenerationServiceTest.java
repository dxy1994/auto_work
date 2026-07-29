package com.auto.trade;

import com.auto.entity.GameItem;
import com.auto.entity.GameItemOrder;
import com.auto.entity.GameItemOrderDetail;
import com.auto.entity.ItemBundleRelation;
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
import static org.junit.jupiter.api.Assertions.assertThrows;
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
        order.setQuantity(8);
        order.setSaleQuantity(3);

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
        ArgumentCaptor<GameItemOrderDetail> saved = ArgumentCaptor.forClass(GameItemOrderDetail.class);
        verify(detailService).save(saved.capture());
        assertEquals(42, saved.getValue().getOrderId());
        assertEquals(9, saved.getValue().getItemId());
        assertEquals("金币", saved.getValue().getItemName());
        assertEquals(3, saved.getValue().getQuantity());
        assertEquals(new BigDecimal("37.50"), saved.getValue().getSubtotal());
        assertEquals(new BigDecimal("37.50"), order.getTotalAmount());
        verify(orderService).updateById(order);
    }

    @Test
    void bundleDetailQuantityMultipliesConfiguredQuantityByPlatformQuantity() {
        GameItemOrder order = new GameItemOrder();
        order.setId(43);
        order.setGameId(7);
        order.setTradeItemName("STARTER_SET");
        order.setQuantity(4);
        order.setSaleQuantity(3);

        GameItem bundle = new GameItem();
        bundle.setId(10);
        bundle.setName("新手套装");
        bundle.setIsBundle(1);

        GameItem child = new GameItem();
        child.setId(11);
        child.setName("恢复药水");
        child.setIsActive(1);
        child.setPrice(new BigDecimal("2.00"));

        ItemBundleRelation relation = new ItemBundleRelation();
        relation.setBundleId(10);
        relation.setItemId(11);
        relation.setQuantity(2);

        when(orderService.getOne(any(), eq(false))).thenReturn(order);
        when(detailService.findByOrderId(43)).thenReturn(List.of());
        when(gameItemService.findActiveByGameIdAndCodeOrName(7, "STARTER_SET"))
                .thenReturn(bundle);
        when(bundleItemService.findRelationsByBundleId(10)).thenReturn(List.of(relation));
        when(gameItemService.listByIds(any())).thenReturn(List.of(child));

        List<GameItemOrderDetail> result = generationService.ensureDetails(order);

        assertEquals(1, result.size());
        assertEquals(6, result.get(0).getQuantity());
        assertEquals(new BigDecimal("12.00"), result.get(0).getSubtotal());
        assertEquals("新手套装", result.get(0).getBundleName());
        assertEquals(new BigDecimal("12.00"), order.getTotalAmount());
    }

    @Test
    void missingPlatformSaleQuantityDoesNotGenerateIncorrectDetail() {
        GameItemOrder order = new GameItemOrder();
        order.setId(44);
        order.setGameId(7);
        order.setTradeItemName("POTION");
        order.setQuantity(5);
        order.setSaleQuantity(0);

        GameItem item = new GameItem();
        item.setId(12);
        item.setName("药水");
        item.setIsBundle(0);
        item.setPrice(BigDecimal.ONE);

        when(orderService.getOne(any(), eq(false))).thenReturn(order);
        when(detailService.findByOrderId(44)).thenReturn(List.of());
        when(gameItemService.findActiveByGameIdAndCodeOrName(7, "POTION")).thenReturn(item);

        IllegalStateException error = assertThrows(
                IllegalStateException.class,
                () -> generationService.ensureDetails(order));

        assertEquals("订单缺少有效的平台已售数量，无法生成子订单", error.getMessage());
        verify(detailService, never()).save(any());
        verify(orderService, never()).updateById(any());
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
