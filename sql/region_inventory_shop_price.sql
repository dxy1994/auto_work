-- 大区库存商铺定价表
-- 将出货价从 game_region_inventory 迁移到本表，按商铺(platform_accounts)独立定价

-- 1. 新建商铺定价表
CREATE TABLE game_region_inventory_shop_price (
    id INT AUTO_INCREMENT PRIMARY KEY,
    inventory_id INT NOT NULL COMMENT '库存记录ID',
    account_id INT NOT NULL COMMENT '商铺ID(关联platform_accounts)',
    selling_price DECIMAL(10,2) NOT NULL DEFAULT 0.00 COMMENT '出货价',
    min_selling_price DECIMAL(10,2) NOT NULL DEFAULT 0.00 COMMENT '最低出货价',
    max_selling_price DECIMAL(10,2) NOT NULL DEFAULT 0.00 COMMENT '最高出货价',
    is_active TINYINT(1) DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE INDEX uk_inventory_account (inventory_id, account_id),
    INDEX idx_account (account_id)
) COMMENT '大区库存商铺定价表';

-- 2. 数据迁移：将现有 game_region_inventory 中的出货价迁移到新表
--    为每个 inventory 记录，在所有活跃 platform_accounts 下创建相同的默认定价
INSERT INTO game_region_inventory_shop_price (inventory_id, account_id, selling_price, min_selling_price, max_selling_price)
SELECT
    inv.id,
    acc.id,
    inv.selling_price,
    inv.min_selling_price,
    inv.max_selling_price
FROM game_region_inventory inv
CROSS JOIN platform_accounts acc
WHERE inv.is_active = 1
  AND acc.is_active = 1
  AND NOT EXISTS (
      SELECT 1 FROM game_region_inventory_shop_price sp
      WHERE sp.inventory_id = inv.id AND sp.account_id = acc.id
  );

-- 3. 清理 game_region_inventory 表中的出货价字段
ALTER TABLE game_region_inventory
    DROP COLUMN selling_price,
    DROP COLUMN min_selling_price,
    DROP COLUMN max_selling_price;
