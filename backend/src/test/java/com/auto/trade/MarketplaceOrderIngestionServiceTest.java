package com.auto.trade;

import com.auto.entity.Account;
import com.auto.entity.GameItemOrder;
import com.auto.entity.GameRegion;
import com.auto.service.AccountService;
import com.auto.service.GameItemOrderService;
import com.auto.service.GameRegionService;
import com.auto.service.TradeEventService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class MarketplaceOrderIngestionServiceTest {

    private GameItemOrderService orderService;
    private MarketplaceOrderIngestionService service;

    @BeforeEach
    void setUp() {
        AccountService accountService = mock(AccountService.class);
        GameRegionService regionService = mock(GameRegionService.class);
        orderService = mock(GameItemOrderService.class);
        TradeEventService eventService = mock(TradeEventService.class);
        service = new MarketplaceOrderIngestionService(
                accountService, regionService, orderService, eventService);

        Account account = new Account();
        account.setId(12);
        account.setWebsiteId(3);
        account.setIsActive(1);
        account.setExtraFields(Map.of(
                "trade_game_id", 9,
                "trade_region_map", Map.of("1", 4)));
        when(accountService.getById(12)).thenReturn(account);

        GameRegion region = new GameRegion();
        region.setId(4);
        region.setGameId(9);
        region.setIsActive(1);
        when(regionService.getById(4)).thenReturn(region);
        when(orderService.save(any(GameItemOrder.class))).thenAnswer(invocation -> {
            GameItemOrder order = invocation.getArgument(0);
            order.setId(55);
            return true;
        });
    }

    @Test
    void createsValidatedAdenaOrderReadyForAssignment() {
        GameItemOrder order = service.ingest(7, 12, message("adena"));

        assertThat(order.getWebsiteId()).isEqualTo(3);
        assertThat(order.getGameId()).isEqualTo(9);
        assertThat(order.getRegionId()).isEqualTo(4);
        assertThat(order.getAssetAmount()).isEqualByComparingTo("2500000");
        assertThat(order.getDeliveryStatus()).isEqualTo("waiting_assignment");
        verify(orderService).save(order);
    }

    @Test
    void repeatedSourceOrderReturnsExistingRow() {
        GameItemOrder existing = new GameItemOrder();
        existing.setId(44);
        when(orderService.findByWebsiteIdAndSourceOrderNo(3, "B-300"))
                .thenReturn(existing);

        assertThat(service.ingest(7, 12, message("adena"))).isSameAs(existing);
        verify(orderService, never()).save(any());
    }

    @Test
    void unknownExternalRegionIsRejectedBeforeInsert() {
        assertThatThrownBy(() -> service.ingest(7, 12, new OrderDetectedMessage(
                "itembay", "B-300", "unknown", "adena",
                new BigDecimal("2500000"), "buyer", "paid", "adena")))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("区服映射");
        verify(orderService, never()).save(any());
    }

    @Test
    void unsupportedAssetIsPersistedAsSuspended() {
        GameItemOrder order = service.ingest(7, 12, message("item"));

        assertThat(order.getDeliveryStatus()).isEqualTo("suspended");
        assertThat(order.getLastErrorCode()).isEqualTo("UNSUPPORTED_ASSET");
    }

    private OrderDetectedMessage message(String assetType) {
        return new OrderDetectedMessage(
                "itembay", "B-300", "1", assetType,
                new BigDecimal("2500000"), "buyer", "paid", "adena");
    }
}
