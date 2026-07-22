package com.auto.trade;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

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
}
