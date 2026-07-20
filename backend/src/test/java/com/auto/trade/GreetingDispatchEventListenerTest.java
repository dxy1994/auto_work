package com.auto.trade;

import org.junit.jupiter.api.Test;

import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;

class GreetingDispatchEventListenerTest {

    @Test
    void delegatesCommittedEventToGreetingService() {
        GreetingDispatchService service = mock(GreetingDispatchService.class);
        GreetingDispatchEventListener listener = new GreetingDispatchEventListener(service);
        GreetingDispatchRequested request = new GreetingDispatchRequested(
                1, 2, 3, 4, 5, 6, "source-7", "itemmania");

        listener.handle(request);

        verify(service).dispatch(1, 2, 3, 4, 5, 6, "source-7", "itemmania");
    }
}
