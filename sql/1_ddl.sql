-- ============================================================
-- 自动化交易系统 数据库初始化脚本（全量 DDL）
-- 合并自: 1_init.sql, 1_central_control.sql
-- ============================================================

SET NAMES utf8mb4;

CREATE DATABASE IF NOT EXISTS `auto_login` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE `auto_login`;

-- ============================================================
-- 一、核心业务表（网站、账号、登录）
-- ============================================================

-- 网站信息表
CREATE TABLE IF NOT EXISTS `websites` (
    `id`           INT AUTO_INCREMENT PRIMARY KEY,
    `name`         VARCHAR(100)  NOT NULL COMMENT '网站名称',
    `url`          VARCHAR(500)  NOT NULL COMMENT '登录页URL',
    `icon`         VARCHAR(500)  COMMENT '网站图标URL',
    `category`     VARCHAR(50)   COMMENT '分类(如：办公/社交/开发)',
    `login_type`   ENUM('form', 'captcha', 'oauth') DEFAULT 'form' COMMENT '登录类型',
    `login_config` JSON          COMMENT '登录配置(表单选择器、字段映射等)',
    `remark`       TEXT          COMMENT '备注',
    `sort_order`   INT           DEFAULT 0 COMMENT '排序',
    `is_active`    TINYINT(1)    DEFAULT 1,
    `created_at`   DATETIME      DEFAULT CURRENT_TIMESTAMP,
    `updated_at`   DATETIME      DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='网站信息表';

-- 账号信息表
CREATE TABLE IF NOT EXISTS `accounts` (
    `id`           INT AUTO_INCREMENT PRIMARY KEY,
    `website_id`   INT           NOT NULL COMMENT '关联网站ID',
    `label`        VARCHAR(100)  NOT NULL COMMENT '账号标签(如：个人/公司)',
    `username`     VARCHAR(200)  NOT NULL,
    `password`     VARCHAR(500)  NOT NULL COMMENT 'AES加密存储',
    `extra_fields` JSON          COMMENT '额外字段(如手机号、邮箱等)',
    `is_default`   TINYINT(1)    DEFAULT 0 COMMENT '是否默认账号',
    `is_active`    TINYINT(1)    DEFAULT 1,
    `created_at`   DATETIME      DEFAULT CURRENT_TIMESTAMP,
    `updated_at`   DATETIME      DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (`website_id`) REFERENCES `websites`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='账号信息表';

-- 登录日志表
CREATE TABLE IF NOT EXISTS `login_logs` (
    `id`           INT AUTO_INCREMENT PRIMARY KEY,
    `website_id`   INT           NOT NULL,
    `account_id`   INT           NOT NULL,
    `status`       ENUM('success', 'failed', 'captcha_required', 'timeout') NOT NULL,
    `message`      VARCHAR(500)  COMMENT '结果描述',
    `duration_ms`  INT           COMMENT '登录耗时(毫秒)',
    `created_at`   DATETIME      DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (`website_id`) REFERENCES `websites`(`id`),
    FOREIGN KEY (`account_id`) REFERENCES `accounts`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='登录日志表';

-- Cookie持久化表
CREATE TABLE IF NOT EXISTS `cookies_store` (
    `id`           INT AUTO_INCREMENT PRIMARY KEY,
    `website_id`   INT           NOT NULL,
    `account_id`   INT           NOT NULL,
    `cookies`      JSON          NOT NULL COMMENT '存储的cookies',
    `expires_at`   DATETIME      COMMENT '过期时间',
    `created_at`   DATETIME      DEFAULT CURRENT_TIMESTAMP,
    `updated_at`   DATETIME      DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (`website_id`) REFERENCES `websites`(`id`),
    FOREIGN KEY (`account_id`) REFERENCES `accounts`(`id`),
    UNIQUE KEY `uk_website_account` (`website_id`, `account_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Cookie持久化表';

-- 账号子功能配置表
CREATE TABLE IF NOT EXISTS `website_schedules` (
    `id`               INT AUTO_INCREMENT PRIMARY KEY,
    `account_id`       INT           NOT NULL COMMENT '关联账号ID',
    `name`             VARCHAR(100)  NOT NULL COMMENT '子功能名',
    `code`             VARCHAR(100)  NOT NULL COMMENT '编码',
    `refresh_interval` INT           DEFAULT -1 COMMENT '刷新频率(秒)，-1表示无需刷新',
    `schedule_type`    VARCHAR(20)   DEFAULT 'none' COMMENT '定时类型: none/once/scheduled',
    `schedule_time`    DATETIME      COMMENT '执行时间(schedule_type=once时使用)',
    `schedule_cron`    VARCHAR(100)  COMMENT '执行间隔(秒)(schedule_type=scheduled时使用)',
    `alert_audio_path` VARCHAR(500)  COMMENT '提醒音频文件本地路径',
    `is_enabled`       TINYINT(1)    DEFAULT 1 COMMENT '是否启用',
    `created_at`       DATETIME      DEFAULT CURRENT_TIMESTAMP,
    `updated_at`       DATETIME      DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (`account_id`) REFERENCES `accounts`(`id`) ON DELETE CASCADE,
    UNIQUE KEY `uk_account_code` (`account_id`, `code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='账号子功能配置表';

-- ============================================================
-- 二、中控平台表（游戏、机器、订单、交易）
-- ============================================================

-- 1. 游戏表
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

-- 2. 游戏大区表
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

-- 3. 游戏物品表（支持套装，父子结构）
--    parent_id 为 NULL 表示单品/套装本身
--    parent_id 不为 NULL 表示该物品属于某个套装的子物品
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

-- 4. 机器表（MAC地址作为唯一标识）
--    ※ 放在订单表之前，因为订单表外键引用此表
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

-- 5. 机器关联游戏表（一台机器可关联多个游戏）
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

-- 6. 游戏账号表
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

-- 7. 游戏物品订单主表
CREATE TABLE IF NOT EXISTS `game_item_orders` (
    `id`            INT AUTO_INCREMENT PRIMARY KEY,
    `order_no`      VARCHAR(64)   NOT NULL COMMENT '订单编号(全局唯一)',
    `website_id`    INT           DEFAULT NULL COMMENT '来源网站ID',
    `source_order_no` VARCHAR(100) DEFAULT NULL COMMENT '平台订单号',
    `game_id`       INT           NOT NULL COMMENT '关联游戏ID',
    `region_id`     INT           NOT NULL COMMENT '关联大区ID',
    `game_account_id` INT         DEFAULT NULL COMMENT '执行游戏账号ID',
    `buyer_character` VARCHAR(100) DEFAULT NULL COMMENT '买家游戏角色名',
    `asset_type`    VARCHAR(32)   NOT NULL DEFAULT 'adena' COMMENT '交付资产类型',
    `asset_amount`  DECIMAL(30,0) DEFAULT NULL COMMENT '交付资产数量',
    `delivery_status` VARCHAR(32) NOT NULL DEFAULT 'detected' COMMENT '自动交付状态',
    `assignment_id` VARCHAR(36)   DEFAULT NULL COMMENT '当前有效指派ID',
    `row_version`   INT           NOT NULL DEFAULT 0 COMMENT '乐观锁版本',
    `customer_name` VARCHAR(100)  COMMENT '客户名称',
    `customer_contact` VARCHAR(200) COMMENT '客户联系方式',
    `total_amount`  DECIMAL(12,2) DEFAULT 0.00 COMMENT '订单总金额',
    `status`        ENUM('pending','assigned','processing','completed','cancelled')
                    DEFAULT 'pending' COMMENT '订单状态: pending=待分配, assigned=已分配, processing=处理中, completed=已完成, cancelled=已取消',
    `assigned_machine_id` INT     DEFAULT NULL COMMENT '分配的机器ID',
    `assigned_at`   DATETIME      COMMENT '分配时间',
    `completed_at`  DATETIME      COMMENT '完成时间',
    `game_delivered_at` DATETIME  COMMENT '游戏交付时间',
    `website_confirmed_at` DATETIME COMMENT '网站确认时间',
    `last_error_code` VARCHAR(64) COMMENT '最后错误编码',
    `last_error_message` VARCHAR(500) COMMENT '最后错误描述',
    `remark`        TEXT          COMMENT '备注',
    `platform_order_time` DATETIME COMMENT '平台原始下单时间',
    `platform_price` DECIMAL(12,2) COMMENT '平台售价(원)',
    `platform_item_type` VARCHAR(32) COMMENT '平台物品分类(게임머니/아이템/계정)',
    `created_at`    DATETIME      DEFAULT CURRENT_TIMESTAMP,
    `updated_at`    DATETIME      DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (`game_id`) REFERENCES `games`(`id`),
    FOREIGN KEY (`region_id`) REFERENCES `game_regions`(`id`),
    FOREIGN KEY (`assigned_machine_id`) REFERENCES `machines`(`id`) ON DELETE SET NULL,
    UNIQUE KEY `uk_order_no` (`order_no`),
    UNIQUE KEY `uk_source_order` (`website_id`, `source_order_no`),
    KEY `idx_status` (`status`),
    KEY `idx_game` (`game_id`),
    KEY `idx_machine` (`assigned_machine_id`),
    KEY `idx_delivery_status` (`delivery_status`),
    KEY `idx_assignment_id` (`assignment_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='游戏物品订单主表';

-- 8. 游戏物品订单子表（订单明细）
CREATE TABLE IF NOT EXISTS `game_item_order_details` (
    `id`            INT AUTO_INCREMENT PRIMARY KEY,
    `order_id`      INT           NOT NULL COMMENT '关联订单主表ID',
    `item_id`       INT           NOT NULL COMMENT '关联游戏物品ID',
    `item_name`     VARCHAR(200)  NOT NULL COMMENT '物品名称(冗余快照)',
    `item_image`    VARCHAR(500)  COMMENT '物品图片(冗余快照)',
    `quantity`      INT           NOT NULL DEFAULT 1 COMMENT '数量',
    `unit_price`    DECIMAL(10,2) DEFAULT 0.00 COMMENT '单价',
    `subtotal`      DECIMAL(12,2) DEFAULT 0.00 COMMENT '小计金额',
    `purchase_price` DECIMAL(10,2) DEFAULT NULL COMMENT '进货价(创建时快照)',
    `selling_price` DECIMAL(10,2) DEFAULT NULL COMMENT '出货价(创建时快照)',
    `status`        ENUM('pending','processing','completed','failed')
                    DEFAULT 'pending' COMMENT '明细状态',
    `remark`        TEXT          COMMENT '备注',
    `created_at`    DATETIME      DEFAULT CURRENT_TIMESTAMP,
    `updated_at`    DATETIME      DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (`order_id`) REFERENCES `game_item_orders`(`id`) ON DELETE CASCADE,
    FOREIGN KEY (`item_id`) REFERENCES `game_items`(`id`),
    KEY `idx_order` (`order_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='游戏物品订单子表';

-- 9. 自动交易指派表
CREATE TABLE IF NOT EXISTS `trade_assignments` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `assignment_id` VARCHAR(36) NOT NULL,
    `order_id` INT NOT NULL,
    `machine_id` INT NOT NULL,
    `game_account_id` INT NOT NULL,
    `status` VARCHAR(24) NOT NULL,
    `token_hash` VARCHAR(64) NOT NULL,
    `lease_expires_at` DATETIME NOT NULL,
    `reject_reason` VARCHAR(255),
    `accepted_at` DATETIME,
    `started_at` DATETIME,
    `finished_at` DATETIME,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY `uk_assignment_id` (`assignment_id`),
    KEY `idx_assignment_order_status` (`order_id`, `status`),
    FOREIGN KEY (`order_id`) REFERENCES `game_item_orders` (`id`),
    FOREIGN KEY (`machine_id`) REFERENCES `machines` (`id`),
    FOREIGN KEY (`game_account_id`) REFERENCES `game_accounts` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='自动交易指派';

-- 10. 自动交易事件日志表
CREATE TABLE IF NOT EXISTS `trade_events` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `order_id` INT NOT NULL,
    `assignment_id` VARCHAR(36),
    `event_type` VARCHAR(64) NOT NULL,
    `from_status` VARCHAR(32),
    `to_status` VARCHAR(32),
    `message` VARCHAR(500),
    `payload` JSON,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    KEY `idx_trade_event_order` (`order_id`, `id`),
    FOREIGN KEY (`order_id`) REFERENCES `game_item_orders` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='自动交易事件日志';

-- 11. 游戏话术表（主游戏默认话术）
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

-- 12. 大区话术表（关联大区，含位置图片）
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

-- 13. 大区物品库存表
CREATE TABLE IF NOT EXISTS `game_region_items` (
    `id`            INT AUTO_INCREMENT PRIMARY KEY,
    `game_id`       INT           NOT NULL COMMENT '关联游戏ID',
    `region_id`     INT           NOT NULL COMMENT '关联大区ID',
    `item_id`       INT           NOT NULL COMMENT '关联物品ID',
    `stock`         INT           NOT NULL DEFAULT 0 COMMENT '库存数量',
    `purchase_price` DECIMAL(10,2) NOT NULL DEFAULT 0.00 COMMENT '当前进货价',
    `selling_price` DECIMAL(10,2) NOT NULL DEFAULT 0.00 COMMENT '当前出货价',
    `min_selling_price` DECIMAL(10,2) NOT NULL DEFAULT 0.00 COMMENT '最小出货价',
    `max_selling_price` DECIMAL(10,2) NOT NULL DEFAULT 0.00 COMMENT '最大出货价',
    `max_fluctuation` DECIMAL(10,2) DEFAULT NULL COMMENT '单次出货最大波动(固定值)',
    `max_fluctuation_rate` DECIMAL(5,2) DEFAULT NULL COMMENT '单次出货最大波动(百分比)',
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

-- ============================================================
-- 增量迁移：game_item_orders 新增 Marketplace 采集字段
-- 兼容 MySQL 8.0.40 以下（不支持 ADD COLUMN IF NOT EXISTS）
-- ============================================================
DELIMITER //
CREATE PROCEDURE IF NOT EXISTS add_order_marketplace_columns()
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'game_item_orders'
          AND COLUMN_NAME = 'platform_order_time'
    ) THEN
        ALTER TABLE game_item_orders
            ADD COLUMN platform_order_time DATETIME COMMENT '平台原始下单时间';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'game_item_orders'
          AND COLUMN_NAME = 'platform_price'
    ) THEN
        ALTER TABLE game_item_orders
            ADD COLUMN platform_price DECIMAL(12,2) COMMENT '平台售价(원)';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'game_item_orders'
          AND COLUMN_NAME = 'platform_item_type'
    ) THEN
        ALTER TABLE game_item_orders
            ADD COLUMN platform_item_type VARCHAR(32) COMMENT '平台物品分类(게임머니/아이템/계정)';
    END IF;
END //
DELIMITER ;

CALL add_order_marketplace_columns();
DROP PROCEDURE IF EXISTS add_order_marketplace_columns;
