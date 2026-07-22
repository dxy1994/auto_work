-- 状态机使用 abnormal 表示招呼阶段需要人工处理，补齐订单状态枚举。
ALTER TABLE game_item_orders
    MODIFY COLUMN status ENUM(
        'pending',
        'assigned',
        'processing',
        'completed',
        'cancelled',
        'abnormal'
    ) NULL DEFAULT 'pending';
