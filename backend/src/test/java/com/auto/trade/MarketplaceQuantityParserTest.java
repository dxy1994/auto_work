package com.auto.trade;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class MarketplaceQuantityParserTest {

    @Test
    void rangeUsesMaximumWithUnitApplied() {
        assertEquals(88_280_000L,
                MarketplaceQuantityParser.parseMaximum(
                        "[30만~8,828만]").orElseThrow());
        assertEquals(9_000L,
                MarketplaceQuantityParser.parseMaximum(
                        "최소 100 최대 9,000").orElseThrow());
    }

    @Test
    void parsesKoreanAndChineseLargeNumberUnits() {
        assertEquals(9_900_000_000L,
                MarketplaceQuantityParser.parseMaximum(
                        "99억 키나").orElseThrow());
        assertEquals(350_000_000L,
                MarketplaceQuantityParser.parseMaximum(
                        "3억5천만").orElseThrow());
        assertEquals(150_000_000L,
                MarketplaceQuantityParser.parseMaximum(
                        "1.5亿").orElseThrow());
    }

    @Test
    void blankOrNonNumericTextIsUnavailable() {
        assertTrue(MarketplaceQuantityParser.parseMaximum("").isEmpty());
        assertTrue(MarketplaceQuantityParser.parseMaximum("분할").isEmpty());
    }
}
