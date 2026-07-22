-- 允许手工取消订单时同步取消其子订单。
ALTER TABLE game_item_order_details
    MODIFY COLUMN status ENUM(
        'pending',
        'processing',
        'completed',
        'failed',
        'cancelled'
    ) NULL DEFAULT 'pending';
