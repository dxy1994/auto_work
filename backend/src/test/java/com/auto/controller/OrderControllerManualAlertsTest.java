package com.auto.controller;

import com.auto.entity.GameItemOrder;
import com.auto.service.GameItemOrderService;
import com.auto.service.TradeAssignmentService;
import com.baomidou.mybatisplus.core.MybatisConfiguration;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.TableInfoHelper;
import org.apache.ibatis.builder.MapperBuilderAssistant;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class OrderControllerManualAlertsTest {

    @BeforeAll
    static void initializeMybatisTableMetadata() {
        TableInfoHelper.initTableInfo(
                new MapperBuilderAssistant(
                        new MybatisConfiguration(),
                        "manual-alert-test"),
                GameItemOrder.class);
    }

    @Test
    @SuppressWarnings({"unchecked", "rawtypes"})
    void waitingAssignmentFailureIsReturnedForVoiceAlert() {
        GameItemOrderService orderService = mock(GameItemOrderService.class);
        TradeAssignmentService assignmentService = mock(TradeAssignmentService.class);
        GameItemOrder order = new GameItemOrder();
        order.setId(45);
        order.setOrderNo("COPY-45");
        order.setDeliveryStatus("waiting_assignment");
        order.setStatus("pending");
        order.setLastErrorCode("GAME_PREPARATION_FAILED");
        order.setLastErrorMessage("物品栏已打开，但未识别到订单物品");
        order.setUpdatedAt(LocalDateTime.of(2026, 7, 27, 18, 5, 2));

        when(orderService.list(any(LambdaQueryWrapper.class))).thenReturn(List.of(order));
        when(orderService.count(any(LambdaQueryWrapper.class))).thenReturn(1L);
        when(assignmentService.list(any(LambdaQueryWrapper.class))).thenReturn(List.of());
        when(assignmentService.count(any(LambdaQueryWrapper.class))).thenReturn(0L);

        OrderController controller = new OrderController(
                orderService,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                assignmentService,
                null,
                null,
                null,
                null,
                null);

        Map<String, Object> response = controller.manualAlerts();

        ArgumentCaptor<LambdaQueryWrapper<GameItemOrder>> queryCaptor =
                ArgumentCaptor.forClass((Class) LambdaQueryWrapper.class);
        verify(orderService).list(queryCaptor.capture());
        LambdaQueryWrapper<GameItemOrder> alertQuery = queryCaptor.getValue();
        assertTrue(alertQuery.getSqlSegment()
                .contains("last_error_code IS NOT NULL"));

        assertEquals(1L, response.get("total"));
        List<Map<String, Object>> items =
                (List<Map<String, Object>>) response.get("items");
        assertEquals(1, items.size());
        assertEquals("订单交易准备失败", items.get(0).get("title"));
        assertEquals("danger", items.get(0).get("severity"));
        assertEquals("GAME_PREPARATION_FAILED", items.get(0).get("error_code"));
    }
}
