package com.auto.trade;

/** 游戏交易完成并提交后，异步发送交易截图并确认网站商品交付。 */
public record GameDeliveryConfirmationRequested(int orderId) {
}
