package com.auto.trade;

import org.junit.jupiter.api.Test;

import java.time.LocalDate;
import java.time.LocalDateTime;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

class MarketplaceOrderIngestionParsingTest {

    @Test
    void extractsItemNameBetweenPercentSigns() {
        assertEquals("游戏币", MarketplaceOrderIngestionService.parseItemFromTitle("VAV%游戏币%快速交易"));
    }

    @Test
    void trimsExtractedItemName() {
        assertEquals("祝福武器卷轴", MarketplaceOrderIngestionService.parseItemFromTitle("商品 % 祝福武器卷轴 % 即时交易"));
    }

    @Test
    void noLongerAcceptsSquareBracketFormat() {
        assertEquals("", MarketplaceOrderIngestionService.parseItemFromTitle("商品[游戏币]快速交易"));
    }

    @Test
    void returnsEmptyForIncompleteOrMissingMarkers() {
        assertEquals("", MarketplaceOrderIngestionService.parseItemFromTitle("商品%游戏币"));
        assertEquals("", MarketplaceOrderIngestionService.parseItemFromTitle("普通商品"));
        assertEquals("", MarketplaceOrderIngestionService.parseItemFromTitle(null));
    }

    @Test
    void parsesItemmaniaFullPlatformOrderTime() {
        assertEquals(
                LocalDateTime.of(2026, 7, 15, 17, 2, 47),
                MarketplaceOrderIngestionService.parsePlatformOrderTime(
                        "2026-07-15 17:02:47"));
    }

    @Test
    void parsesLegacyPlatformOrderTimeWithoutYear() {
        LocalDateTime now = LocalDateTime.now();
        int expectedYear = LocalDate.now().getYear();
        LocalDateTime currentYearValue =
                LocalDateTime.of(expectedYear, 1, 15, 17, 2);
        if (currentYearValue.isAfter(now.plusDays(1))) {
            expectedYear--;
        }

        LocalDateTime parsed =
                MarketplaceOrderIngestionService.parsePlatformOrderTime(
                        "01-15 17:02");

        assertEquals(expectedYear, parsed.getYear());
        assertEquals(1, parsed.getMonthValue());
        assertEquals(15, parsed.getDayOfMonth());
        assertEquals(17, parsed.getHour());
        assertEquals(2, parsed.getMinute());
    }

    @Test
    void rejectsInvalidPlatformOrderTime() {
        assertNull(MarketplaceOrderIngestionService.parsePlatformOrderTime(
                "not-a-time"));
    }
}
