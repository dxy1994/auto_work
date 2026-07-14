-- 中控平台 数据库扩展脚本

SET NAMES utf8mb4;
USE `auto_login`;

-- ============================================================
-- 1. 游戏表
-- ============================================================
CREATE TABLE IF NOT EXISTS `games` (
    `id`           INT AUTO_INCREMENT PRIMARY KEY,
    `name`         VARCHAR(100)  NOT NULL COMMENT '游戏名称',
    `code`         VARCHAR(50)   NOT NULL COMMENT '游戏编码(唯一标识)',
    `icon`         VARCHAR(500)  COMMENT '游戏图标URL',
    `platform`     VARCHAR(50)   COMMENT '平台(PC/手游/主机)',
    `remark`       TEXT          COMMENT '备注',
    `sort_order`   INT           DEFAULT 0 COMMENT '排序',
    `is_active`    TINYINT(1)    DEFAULT 1,
    `created_at`   DATETIME      DEFAULT CURRENT_TIMESTAMP,
    `updated_at`   DATETIME      DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY `uk_code` (`code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='游戏表';

-- ============================================================
-- 2. 游戏大区表
-- ============================================================
CREATE TABLE IF NOT EXISTS `game_regions` (
    `id`           INT AUTO_INCREMENT PRIMARY KEY,
    `game_id`      INT           NOT NULL COMMENT '关联游戏ID',
    `name`         VARCHAR(100)  NOT NULL COMMENT '大区名称',
    `code`         VARCHAR(50)   NOT NULL COMMENT '大区编码',
    `sort_order`   INT           DEFAULT 0 COMMENT '排序',
    `is_active`    TINYINT(1)    DEFAULT 1,
    `created_at`   DATETIME      DEFAULT CURRENT_TIMESTAMP,
    `updated_at`   DATETIME      DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (`game_id`) REFERENCES `games`(`id`) ON DELETE CASCADE,
    UNIQUE KEY `uk_game_region` (`game_id`, `code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='游戏大区表';

-- ============================================================
-- 3. 游戏物品表（支持套装，父子结构）
--    parent_id 为 NULL 表示单品/套装本身
--    parent_id 不为 NULL 表示该物品属于某个套装的子物品
-- ============================================================
CREATE TABLE IF NOT EXISTS `game_items` (
    `id`           INT AUTO_INCREMENT PRIMARY KEY,
    `game_id`      INT           NOT NULL COMMENT '关联游戏ID',
    `parent_id`    INT           DEFAULT NULL COMMENT '父物品ID(套装时为NULL，子物品指向套装ID)',
    `name`         VARCHAR(200)  NOT NULL COMMENT '物品名称',
    `code`         VARCHAR(100)  NOT NULL COMMENT '物品编码',
    `image`        VARCHAR(500)  COMMENT '商品图片URL',
    `is_bundle`    TINYINT(1)    DEFAULT 0 COMMENT '是否为套装(1=套装, 0=单品)',
    `category`     VARCHAR(100)  COMMENT '物品分类',
    `price`        DECIMAL(10,2) DEFAULT 0.00 COMMENT '参考价格',
    `remark`       TEXT          COMMENT '备注',
    `sort_order`   INT           DEFAULT 0 COMMENT '排序',
    `is_active`    TINYINT(1)    DEFAULT 1,
    `created_at`   DATETIME      DEFAULT CURRENT_TIMESTAMP,
    `updated_at`   DATETIME      DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (`game_id`) REFERENCES `games`(`id`) ON DELETE CASCADE,
    FOREIGN KEY (`parent_id`) REFERENCES `game_items`(`id`) ON DELETE SET NULL,
    UNIQUE KEY `uk_game_item` (`game_id`, `code`),
    KEY `idx_parent` (`parent_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='游戏物品表';

-- ============================================================
-- 4. 机器表（MAC地址作为唯一标识）
--    ※ 放在订单表之前，因为订单表外键引用此表
-- ============================================================
CREATE TABLE IF NOT EXISTS `machines` (
    `id`            INT AUTO_INCREMENT PRIMARY KEY,
    `mac_address`   VARCHAR(17)   NOT NULL COMMENT 'MAC地址(唯一标识, 格式: AA:BB:CC:DD:EE:FF)',
    `hostname`      VARCHAR(100)  COMMENT '机器主机名',
    `ip_address`    VARCHAR(45)   COMMENT 'IP地址',
    `name`          VARCHAR(100)  COMMENT '机器别名/标签',
    `os_info`       VARCHAR(200)  COMMENT '操作系统信息',
    `status`        ENUM('online','offline','busy','disabled')
                    DEFAULT 'offline' COMMENT '机器状态',
    `last_heartbeat` DATETIME     COMMENT '最后心跳时间',
    `remark`        TEXT          COMMENT '备注',
    `is_active`     TINYINT(1)    DEFAULT 1,
    `created_at`    DATETIME      DEFAULT CURRENT_TIMESTAMP,
    `updated_at`    DATETIME      DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY `uk_mac` (`mac_address`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='机器表';

-- ============================================================
-- 5. 机器关联游戏表（一台机器可关联多个游戏）
-- ============================================================
CREATE TABLE IF NOT EXISTS `machine_games` (
    `id`            INT AUTO_INCREMENT PRIMARY KEY,
    `machine_id`    INT           NOT NULL COMMENT '关联机器ID',
    `game_id`       INT           NOT NULL COMMENT '关联游戏ID',
    `priority`      INT           DEFAULT 0 COMMENT '优先级(数字越大优先级越高)',
    `max_concurrent` INT          DEFAULT 1 COMMENT '最大并发订单数',
    `is_active`     TINYINT(1)    DEFAULT 1,
    `created_at`    DATETIME      DEFAULT CURRENT_TIMESTAMP,
    `updated_at`    DATETIME      DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (`machine_id`) REFERENCES `machines`(`id`) ON DELETE CASCADE,
    FOREIGN KEY (`game_id`) REFERENCES `games`(`id`) ON DELETE CASCADE,
    UNIQUE KEY `uk_machine_game` (`machine_id`, `game_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='机器关联游戏表';

-- ============================================================
-- 6. 游戏账号表
-- ============================================================
CREATE TABLE IF NOT EXISTS `game_accounts` (
    `id`            INT AUTO_INCREMENT PRIMARY KEY,
    `game_id`       INT           NOT NULL COMMENT '关联游戏ID',
    `region_id`     INT           DEFAULT NULL COMMENT '关联大区ID(NULL表示通用)',
    `machine_id`    INT           DEFAULT NULL COMMENT '绑定机器ID(NULL表示未绑定)',
    `account_name`  VARCHAR(200)  NOT NULL COMMENT '账号名',
    `account_no`    VARCHAR(200)  NOT NULL COMMENT '账号(加密存储)',
    `password`      VARCHAR(500)  NOT NULL COMMENT '密码(加密存储)',
    `nickname`      VARCHAR(100)  COMMENT '游戏内昵称',
    `level`         VARCHAR(50)   COMMENT '账号等级',
    `extra_fields`  JSON          COMMENT '额外字段(手机、邮箱等)',
    `status`        ENUM('idle','in_use','locked','disabled')
                    DEFAULT 'idle' COMMENT '账号状态',
    `is_active`     TINYINT(1)    DEFAULT 1,
    `created_at`    DATETIME      DEFAULT CURRENT_TIMESTAMP,
    `updated_at`    DATETIME      DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (`game_id`) REFERENCES `games`(`id`) ON DELETE CASCADE,
    FOREIGN KEY (`region_id`) REFERENCES `game_regions`(`id`) ON DELETE SET NULL,
    FOREIGN KEY (`machine_id`) REFERENCES `machines`(`id`) ON DELETE SET NULL,
    KEY `idx_game` (`game_id`),
    KEY `idx_machine` (`machine_id`),
    KEY `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='游戏账号表';

-- ============================================================
-- 7. 游戏物品订单主表
-- ============================================================
CREATE TABLE IF NOT EXISTS `game_item_orders` (
    `id`            INT AUTO_INCREMENT PRIMARY KEY,
    `order_no`      VARCHAR(64)   NOT NULL COMMENT '订单编号(全局唯一)',
    `game_id`       INT           NOT NULL COMMENT '关联游戏ID',
    `region_id`     INT           NOT NULL COMMENT '关联大区ID',
    `customer_name` VARCHAR(100)  COMMENT '客户名称',
    `customer_contact` VARCHAR(200) COMMENT '客户联系方式',
    `total_amount`  DECIMAL(12,2) DEFAULT 0.00 COMMENT '订单总金额',
    `status`        ENUM('pending','assigned','processing','completed','cancelled')
                    DEFAULT 'pending' COMMENT '订单状态: pending=待分配, assigned=已分配, processing=处理中, completed=已完成, cancelled=已取消',
    `assigned_machine_id` INT     DEFAULT NULL COMMENT '分配的机器ID',
    `assigned_at`   DATETIME      COMMENT '分配时间',
    `completed_at`  DATETIME      COMMENT '完成时间',
    `remark`        TEXT          COMMENT '备注',
    `created_at`    DATETIME      DEFAULT CURRENT_TIMESTAMP,
    `updated_at`    DATETIME      DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (`game_id`) REFERENCES `games`(`id`),
    FOREIGN KEY (`region_id`) REFERENCES `game_regions`(`id`),
    FOREIGN KEY (`assigned_machine_id`) REFERENCES `machines`(`id`) ON DELETE SET NULL,
    UNIQUE KEY `uk_order_no` (`order_no`),
    KEY `idx_status` (`status`),
    KEY `idx_game` (`game_id`),
    KEY `idx_machine` (`assigned_machine_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='游戏物品订单主表';

-- ============================================================
-- 8. 游戏物品订单子表（订单明细）
-- ============================================================
CREATE TABLE IF NOT EXISTS `game_item_order_details` (
    `id`            INT AUTO_INCREMENT PRIMARY KEY,
    `order_id`      INT           NOT NULL COMMENT '关联订单主表ID',
    `item_id`       INT           NOT NULL COMMENT '关联游戏物品ID',
    `item_name`     VARCHAR(200)  NOT NULL COMMENT '物品名称(冗余快照)',
    `item_image`    VARCHAR(500)  COMMENT '物品图片(冗余快照)',
    `quantity`      INT           NOT NULL DEFAULT 1 COMMENT '数量',
    `unit_price`    DECIMAL(10,2) DEFAULT 0.00 COMMENT '单价',
    `subtotal`      DECIMAL(12,2) DEFAULT 0.00 COMMENT '小计金额',
    `status`        ENUM('pending','processing','completed','failed')
                    DEFAULT 'pending' COMMENT '明细状态',
    `remark`        TEXT          COMMENT '备注',
    `created_at`    DATETIME      DEFAULT CURRENT_TIMESTAMP,
    `updated_at`    DATETIME      DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (`order_id`) REFERENCES `game_item_orders`(`id`) ON DELETE CASCADE,
    FOREIGN KEY (`item_id`) REFERENCES `game_items`(`id`),
    KEY `idx_order` (`order_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='游戏物品订单子表';

-- ============================================================
-- 9. 游戏话术表（主游戏默认话术）
-- ============================================================
CREATE TABLE IF NOT EXISTS `game_scripts` (
    `id`           INT AUTO_INCREMENT PRIMARY KEY,
    `game_id`      INT           NOT NULL COMMENT '关联游戏ID',
    `title`        VARCHAR(200)  NOT NULL COMMENT '话术标题',
    `content`      TEXT          NOT NULL COMMENT '话术内容',
    `category`     VARCHAR(100)  COMMENT '话术分类(如：招呼、促单、售后)',
    `sort_order`   INT           DEFAULT 0 COMMENT '排序',
    `is_active`    TINYINT(1)    DEFAULT 1,
    `created_at`   DATETIME      DEFAULT CURRENT_TIMESTAMP,
    `updated_at`   DATETIME      DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (`game_id`) REFERENCES `games`(`id`) ON DELETE CASCADE,
    KEY `idx_game` (`game_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='游戏话术表';

-- ============================================================
-- 10. 大区话术表（关联大区，含位置图片）
-- ============================================================
CREATE TABLE IF NOT EXISTS `region_scripts` (
    `id`           INT AUTO_INCREMENT PRIMARY KEY,
    `region_id`    INT           NOT NULL COMMENT '关联大区ID',
    `game_script_id` INT         DEFAULT NULL COMMENT '关联游戏话术ID(NULL表示独立话术)',
    `title`        VARCHAR(200)  NOT NULL COMMENT '话术标题',
    `content`      TEXT          NOT NULL COMMENT '话术内容',
    `position_image` VARCHAR(500) COMMENT '位置图片URL',
    `category`     VARCHAR(100)  COMMENT '话术分类',
    `sort_order`   INT           DEFAULT 0 COMMENT '排序',
    `is_active`    TINYINT(1)    DEFAULT 1,
    `created_at`   DATETIME      DEFAULT CURRENT_TIMESTAMP,
    `updated_at`   DATETIME      DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (`region_id`) REFERENCES `game_regions`(`id`) ON DELETE CASCADE,
    FOREIGN KEY (`game_script_id`) REFERENCES `game_scripts`(`id`) ON DELETE SET NULL,
    KEY `idx_region` (`region_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='大区话术表';

-- ============================================================
-- 11. 大区物品库存表
-- ============================================================
CREATE TABLE IF NOT EXISTS `game_region_items` (
    `id`            INT AUTO_INCREMENT PRIMARY KEY,
    `game_id`       INT           NOT NULL COMMENT '关联游戏ID',
    `region_id`     INT           NOT NULL COMMENT '关联大区ID',
    `item_id`       INT           NOT NULL COMMENT '关联物品ID',
    `stock`         INT           NOT NULL DEFAULT 0 COMMENT '库存数量',
    `is_active`     TINYINT(1)    DEFAULT 1,
    `created_at`    DATETIME      DEFAULT CURRENT_TIMESTAMP,
    `updated_at`    DATETIME      DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (`game_id`) REFERENCES `games`(`id`) ON DELETE CASCADE,
    FOREIGN KEY (`region_id`) REFERENCES `game_regions`(`id`) ON DELETE CASCADE,
    FOREIGN KEY (`item_id`) REFERENCES `game_items`(`id`) ON DELETE CASCADE,
    UNIQUE KEY `uk_region_item` (`region_id`, `item_id`),
    KEY `idx_game` (`game_id`),
    KEY `idx_region` (`region_id`),
    KEY `idx_item` (`item_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='大区物品库存表';
