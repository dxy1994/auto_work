ALTER TABLE game_regions
    ADD COLUMN select_x INT NULL COMMENT '800x600客户端内的大区选择X坐标' AFTER sort_order,
    ADD COLUMN select_y INT NULL COMMENT '800x600客户端内的大区选择Y坐标' AFTER select_x;
