package com.auto.trade;

import com.auto.entity.Game;
import com.auto.entity.GameItemOrder;
import com.auto.entity.GameRegion;
import com.auto.entity.PlatformAccount;
import com.auto.service.GameItemOrderService;
import com.auto.service.GameRegionService;
import com.auto.service.GameService;
import com.auto.service.PlatformAccountService;
import com.auto.service.TradeEventService;
import org.junit.jupiter.api.Test;
import org.springframework.context.ApplicationEventPublisher;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class MarketplaceOrderIngestionRecoveryTest {

    @Test
    void repeatedBarotemObservationRepairsSpacedGameNameMapping() {
        PlatformAccountService accountService = mock(PlatformAccountService.class);
        GameRegionService regionService = mock(GameRegionService.class);
        GameItemOrderService orderService = mock(GameItemOrderService.class);
        TradeEventService eventService = mock(TradeEventService.class);
        GameService gameService = mock(GameService.class);
        ApplicationEventPublisher publisher = mock(ApplicationEventPublisher.class);
        OrderDetailGenerationService detailGenerationService =
                mock(OrderDetailGenerationService.class);
        MarketplaceOrderIngestionService service =
                new MarketplaceOrderIngestionService(
                        accountService,
                        regionService,
                        orderService,
                        eventService,
                        gameService,
                        publisher,
                        detailGenerationService);

        PlatformAccount account = new PlatformAccount();
        account.setId(11);
        account.setWebsiteId(2);
        account.setIsActive(1);
        account.setExtraFields(Map.of());
        GameItemOrder existing = new GameItemOrder();
        existing.setId(73);
        existing.setWebsiteId(2);
        existing.setPlatformAccountId(11);
        existing.setSourceOrderNo("178583752411285073-61");
        existing.setGameId(-1);
        existing.setRegionId(-1);
        existing.setDeliveryStatus("suspended");
        existing.setLastErrorCode("CONFIG_MISSING");

        Game game = new Game();
        game.setId(1);
        game.setCode("리니지클래식");
        game.setName("天堂经典版");
        GameRegion region = new GameRegion();
        region.setId(14);
        region.setGameId(1);
        region.setCode("군터");

        when(accountService.getById(11)).thenReturn(account);
        when(orderService.findByWebsiteIdAndSourceOrderNo(
                2, "178583752411285073-61")).thenReturn(existing);
        when(gameService.findByCode("리니지 클래식")).thenReturn(null);
        when(gameService.findAllActiveOrdered()).thenReturn(List.of(game));
        when(regionService.findByGameIdAndCode(1, "군터")).thenReturn(region);

        GameItemOrder result = service.ingest(
                7,
                11,
                new OrderDetectedMessage(
                        "barotem",
                        "178583752411285073-61",
                        "군터",
                        "adena",
                        new BigDecimal("100000"),
                        "은하수",
                        "trading",
                        "%아데나% 빠른거래",
                        "리니지 클래식",
                        "26년 08월 04일 18:58:47",
                        new BigDecimal("9800"),
                        "money",
                        "%아데나% 빠른거래",
                        100000,
                        100000));

        assertEquals(1, result.getGameId());
        assertEquals(14, result.getRegionId());
        assertEquals("greeting", result.getDeliveryStatus());
        assertEquals(new BigDecimal("100000"), result.getAssetAmount());
        assertNull(result.getLastErrorCode());
        assertNull(result.getLastErrorMessage());
        verify(orderService).updateById(existing);
        verify(detailGenerationService).ensureDetails(existing);
        verify(eventService).save(any());
        verify(publisher).publishEvent(any(GreetingDispatchRequested.class));
    }
}
