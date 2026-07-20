-- 已有数据库升级：记录订单实际来源平台账号，避免重新招呼时串号。
ALTER TABLE `game_item_orders`
    ADD COLUMN IF NOT EXISTS `platform_account_id` int NULL COMMENT '来源平台账号ID' AFTER `website_id`;

SET @idx_exists = (
    SELECT COUNT(1)
    FROM information_schema.statistics
    WHERE table_schema = DATABASE()
      AND table_name = 'game_item_orders'
      AND index_name = 'idx_platform_account_id'
);
SET @idx_sql = IF(
    @idx_exists = 0,
    'CREATE INDEX `idx_platform_account_id` ON `game_item_orders` (`platform_account_id`)',
    'SELECT 1'
);
PREPARE idx_stmt FROM @idx_sql;
EXECUTE idx_stmt;
DEALLOCATE PREPARE idx_stmt;
