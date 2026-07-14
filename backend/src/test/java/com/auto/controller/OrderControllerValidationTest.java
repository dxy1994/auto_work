package com.auto.controller;

import com.auto.common.ApiException;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertThrows;

class OrderControllerValidationTest {

    private final OrderController controller = new OrderController(null, null, null, null, null);

    @Test
    void createRejectsMissingRequiredFieldsAndEmptyDetailsBeforeDatabaseAccess() {
        assertThrows(ApiException.class, () -> controller.create(new OrderController.OrderCreate()));
    }

    @Test
    void createRejectsNonPositiveQuantityAndNegativePriceBeforeDatabaseAccess() {
        OrderController.OrderCreate zeroQuantity = validCreate();
        zeroQuantity.details.get(0).quantity = 0;
        assertThrows(ApiException.class, () -> controller.create(zeroQuantity));

        OrderController.OrderCreate negativePrice = validCreate();
        negativePrice.details.get(0).unitPrice = new BigDecimal("-0.01");
        assertThrows(ApiException.class, () -> controller.create(negativePrice));
    }

    @Test
    void updateRejectsUnknownOrderStatusBeforeDatabaseAccess() {
        OrderController.OrderUpdate payload = new OrderController.OrderUpdate();
        payload.status = "unknown";
        assertThrows(ApiException.class, () -> controller.update(1, payload));
    }

    @Test
    void updateDetailRejectsInvalidQuantityBeforeDatabaseAccess() {
        OrderController.OrderDetailUpdate payload = new OrderController.OrderDetailUpdate();
        payload.quantity = -1;
        assertThrows(ApiException.class, () -> controller.updateDetail(1, payload));
    }

    private OrderController.OrderCreate validCreate() {
        OrderController.OrderDetailCreate detail = new OrderController.OrderDetailCreate();
        detail.itemId = 1;
        OrderController.OrderCreate payload = new OrderController.OrderCreate();
        payload.gameId = 1;
        payload.regionId = 1;
        payload.details = List.of(detail);
        return payload;
    }
}
