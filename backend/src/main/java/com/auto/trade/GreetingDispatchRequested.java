package com.auto.trade;

/**
 * 招呼派发请求。事务内发布时，监听器会等事务提交后再异步执行。
 */
public record GreetingDispatchRequested(
        int machineId,
        int orderId,
        int gameId,
        int regionId,
        int websiteId,
        int accountId,
        String sourceOrderNo,
        String platform) {
}
