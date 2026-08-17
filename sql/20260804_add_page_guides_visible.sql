-- 页面使用说明由系统控制统一决定是否展示，默认保持开启以兼容现有行为。
SET @page_guides_visible_exists = (
    SELECT COUNT(*)
    FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'system_controls'
      AND column_name = 'page_guides_visible'
);

SET @add_page_guides_visible = IF(
    @page_guides_visible_exists = 0,
    'ALTER TABLE system_controls ADD COLUMN page_guides_visible TINYINT NOT NULL DEFAULT 1 AFTER auto_game_trade_enabled',
    'SELECT 1'
);
PREPARE add_page_guides_visible_stmt FROM @add_page_guides_visible;
EXECUTE add_page_guides_visible_stmt;
DEALLOCATE PREPARE add_page_guides_visible_stmt;
