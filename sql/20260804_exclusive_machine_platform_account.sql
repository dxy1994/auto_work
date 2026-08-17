-- 同一平台账号在任意时刻只能关联一台机器。
-- MySQL 唯一索引允许多个 NULL，因此停用记录不会阻止账号之后重新关联。
SET @binding_table_exists = (
    SELECT COUNT(*)
    FROM information_schema.tables
    WHERE table_schema = DATABASE()
      AND table_name = 'machine_platform_accounts'
);

SET @active_account_column_exists = (
    SELECT COUNT(*)
    FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'machine_platform_accounts'
      AND column_name = 'active_account_id'
);

SET @add_active_account_column = IF(
    @binding_table_exists = 1 AND @active_account_column_exists = 0,
    'ALTER TABLE machine_platform_accounts ADD COLUMN active_account_id INT GENERATED ALWAYS AS (CASE WHEN is_active = 1 THEN account_id ELSE NULL END) STORED',
    'SELECT 1'
);
PREPARE add_active_account_column_stmt FROM @add_active_account_column;
EXECUTE add_active_account_column_stmt;
DEALLOCATE PREPARE add_active_account_column_stmt;

SET @active_account_index_exists = (
    SELECT COUNT(*)
    FROM information_schema.statistics
    WHERE table_schema = DATABASE()
      AND table_name = 'machine_platform_accounts'
      AND index_name = 'uk_machine_platform_account_active'
);

SET @add_active_account_index = IF(
    @binding_table_exists = 1 AND @active_account_index_exists = 0,
    'ALTER TABLE machine_platform_accounts ADD UNIQUE KEY uk_machine_platform_account_active (active_account_id)',
    'SELECT 1'
);
PREPARE add_active_account_index_stmt FROM @add_active_account_index;
EXECUTE add_active_account_index_stmt;
DEALLOCATE PREPARE add_active_account_index_stmt;
