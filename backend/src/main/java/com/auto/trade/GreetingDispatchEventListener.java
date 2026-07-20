package com.auto.trade;

import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Component;
import org.springframework.transaction.event.TransactionPhase;
import org.springframework.transaction.event.TransactionalEventListener;

/** 事务提交后异步执行招呼，保证新订单对派发线程可见。 */
@Component
public class GreetingDispatchEventListener {

    private final GreetingDispatchService greetingDispatchService;

    public GreetingDispatchEventListener(GreetingDispatchService greetingDispatchService) {
        this.greetingDispatchService = greetingDispatchService;
    }

    @Async
    @TransactionalEventListener(
            phase = TransactionPhase.AFTER_COMMIT,
            fallbackExecution = true)
    public void handle(GreetingDispatchRequested request) {
        greetingDispatchService.dispatch(
                request.machineId(),
                request.orderId(),
                request.gameId(),
                request.regionId(),
                request.websiteId(),
                request.accountId(),
                request.sourceOrderNo(),
                request.platform());
    }
}
