package com.auto.trade;

import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Component;
import org.springframework.transaction.event.TransactionPhase;
import org.springframework.transaction.event.TransactionalEventListener;

/** 订单进入等待网站确认后，再异步启动截图发送和网站交付确认。 */
@Component
public class GameDeliveryConfirmationEventListener {

    private final DeliveryConfirmationService deliveryConfirmationService;

    public GameDeliveryConfirmationEventListener(
            DeliveryConfirmationService deliveryConfirmationService) {
        this.deliveryConfirmationService = deliveryConfirmationService;
    }

    @Async
    @TransactionalEventListener(
            phase = TransactionPhase.AFTER_COMMIT,
            fallbackExecution = true)
    public void handle(GameDeliveryConfirmationRequested request) {
        deliveryConfirmationService.dispatch(request.orderId());
    }
}
