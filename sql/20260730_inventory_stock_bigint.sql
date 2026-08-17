ALTER TABLE game_region_inventory
    MODIFY COLUMN stock BIGINT NOT NULL DEFAULT 0;

ALTER TABLE inventory_change_log
    MODIFY COLUMN stock_before BIGINT NULL,
    MODIFY COLUMN stock_after BIGINT NULL,
    MODIFY COLUMN stock_delta BIGINT NULL;
