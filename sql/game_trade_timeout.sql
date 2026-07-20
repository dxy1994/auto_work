-- 游戏级交易等待超时。重复执行安全，已有数据库会补齐字段。
SET @trade_timeout_column_exists = (
    SELECT COUNT(1)
    FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'games'
      AND column_name = 'trade_timeout_seconds'
);
SET @trade_timeout_ddl = IF(
    @trade_timeout_column_exists = 0,
    'ALTER TABLE `games` ADD COLUMN `trade_timeout_seconds` INT NOT NULL DEFAULT 300 COMMENT ''等待买家交易申请超时秒数'' AFTER `trade_type`',
    'SELECT 1'
);
PREPARE trade_timeout_stmt FROM @trade_timeout_ddl;
EXECUTE trade_timeout_stmt;
DEALLOCATE PREPARE trade_timeout_stmt;

UPDATE `games`
SET `trade_timeout_seconds` = 300
WHERE `trade_timeout_seconds` IS NULL
   OR `trade_timeout_seconds` < 30
   OR `trade_timeout_seconds` > 7200;
