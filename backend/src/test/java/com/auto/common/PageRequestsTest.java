package com.auto.common;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

class PageRequestsTest {

    @Test
    void convertsOneBasedPageToMyBatisPlusPage() {
        var request = PageRequests.of(2, 50);

        assertEquals(2, request.getCurrent());
        assertEquals(50, request.getSize());
    }

    @Test
    void rejectsInvalidOrExcessivePagination() {
        assertThrows(ApiException.class, () -> PageRequests.of(0, 20));
        assertThrows(ApiException.class, () -> PageRequests.of(1, 0));
        assertThrows(ApiException.class, () -> PageRequests.of(1, 201));
        assertThrows(ApiException.class, () -> PageRequests.limit(0));
        assertThrows(ApiException.class, () -> PageRequests.limit(201));
    }
}
