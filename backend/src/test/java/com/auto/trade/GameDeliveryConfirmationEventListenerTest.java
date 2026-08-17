package com.auto.trade;

import org.junit.jupiter.api.Test;

import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;

class GameDeliveryConfirmationEventListenerTest {

    @Test
    void delegatesCommittedEventToDeliveryConfirmationService() {
        DeliveryConfirmationService service = mock(DeliveryConfirmationService.class);
        GameDeliveryConfirmationEventListener listener =
                new GameDeliveryConfirmationEventListener(service);

        listener.handle(new GameDeliveryConfirmationRequested(42));

        verify(service).dispatch(42);
    }
}
