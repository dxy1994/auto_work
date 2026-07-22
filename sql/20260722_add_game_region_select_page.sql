-- 游戏客户端的服务器列表可能分页；记录每个大区所在页，执行端每次交易据此重新选区。
ALTER TABLE game_regions
    ADD COLUMN select_page INT NOT NULL DEFAULT 1 COMMENT '游戏客户端服务器列表页码，从1开始'
    AFTER select_y;
