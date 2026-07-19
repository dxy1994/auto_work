-- 库存变更审计日志表
CREATE TABLE IF NOT EXISTS inventory_change_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    inventory_id INT NOT NULL COMMENT '库存记录ID',
    game_id INT NOT NULL COMMENT '游戏ID',
    region_id INT NOT NULL COMMENT '大区ID',
    item_id INT NOT NULL COMMENT '物品ID',
    change_type VARCHAR(50) NOT NULL COMMENT '变更类型: stock_in/stock_out/price_update/fluctuation_update/system_sync/initialization',
    stock_before INT COMMENT '变更前库存',
    stock_after INT COMMENT '变更后库存',
    stock_delta INT COMMENT '库存变化量(正数入库/负数出库)',
    unit_price DECIMAL(10,2) COMMENT '入库单价(仅入库时记录)',
    avg_price_before DECIMAL(10,2) COMMENT '变更前均价',
    avg_price_after DECIMAL(10,2) COMMENT '变更后均价',
    change_reason VARCHAR(500) COMMENT '变更原因(出库时必填)',
    operator VARCHAR(100) COMMENT '操作者',
    related_order_id INT COMMENT '关联订单ID',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_inventory_id (inventory_id),
    INDEX idx_created_at (created_at),
    INDEX idx_change_type (change_type)
) COMMENT '库存变更审计日志';
