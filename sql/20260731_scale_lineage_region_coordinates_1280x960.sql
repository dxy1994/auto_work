-- 天堂经典版客户区从 800x600 等比调整为 1280x960 后执行一次。
-- 本迁移不是幂等的；已经录入 1280x960 坐标的环境不要重复执行。
UPDATE game_regions AS gr
JOIN games AS g ON g.id = gr.game_id
SET gr.select_x = ROUND(gr.select_x * 1.6),
    gr.select_y = ROUND(gr.select_y * 1.6)
WHERE HEX(g.code) = 'EBA6ACEB8B88ECA780ED81B4EB9E98EC8B9D'
  AND gr.select_x IS NOT NULL
  AND gr.select_y IS NOT NULL;
