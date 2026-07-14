-- Lineage Classic 自动交易基础迁移（仅执行一次）

SET NAMES utf8mb4;
USE `auto_login`;

ALTER TABLE `game_item_orders`
    ADD COLUMN `website_id` INT NULL COMMENT '来源网站ID',
    ADD COLUMN `source_order_no` VARCHAR(100) NULL COMMENT '平台订单号',
    ADD COLUMN `game_account_id` INT NULL COMMENT '执行游戏账号ID',
    ADD COLUMN `buyer_character` VARCHAR(100) NULL COMMENT '买家游戏角色名',
    ADD COLUMN `asset_type` VARCHAR(32) NOT NULL DEFAULT 'adena' COMMENT '交付资产类型',
    ADD COLUMN `asset_amount` DECIMAL(30,0) NULL COMMENT '交付资产数量',
    ADD COLUMN `delivery_status` VARCHAR(32) NOT NULL DEFAULT 'detected' COMMENT '自动交付状态',
    ADD COLUMN `assignment_id` VARCHAR(36) NULL COMMENT '当前有效指派ID',
    ADD COLUMN `row_version` INT NOT NULL DEFAULT 0 COMMENT '乐观锁版本',
    ADD COLUMN `game_delivered_at` DATETIME NULL COMMENT '游戏交付时间',
    ADD COLUMN `website_confirmed_at` DATETIME NULL COMMENT '网站确认时间',
    ADD COLUMN `last_error_code` VARCHAR(64) NULL COMMENT '最后错误编码',
    ADD COLUMN `last_error_message` VARCHAR(500) NULL COMMENT '最后错误描述',
    ADD UNIQUE KEY `uk_source_order` (`website_id`, `source_order_no`),
    ADD KEY `idx_delivery_status` (`delivery_status`),
    ADD KEY `idx_assignment_id` (`assignment_id`);

CREATE TABLE IF NOT EXISTS `trade_assignments` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `assignment_id` VARCHAR(36) NOT NULL,
    `order_id` INT NOT NULL,
    `machine_id` INT NOT NULL,
    `game_account_id` INT NOT NULL,
    `status` VARCHAR(24) NOT NULL,
    `token_hash` VARCHAR(64) NOT NULL,
    `lease_expires_at` DATETIME NOT NULL,
    `reject_reason` VARCHAR(255) NULL,
    `accepted_at` DATETIME NULL,
    `started_at` DATETIME NULL,
    `finished_at` DATETIME NULL,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY `uk_assignment_id` (`assignment_id`),
    KEY `idx_assignment_order_status` (`order_id`, `status`),
    CONSTRAINT `fk_trade_assignment_order` FOREIGN KEY (`order_id`) REFERENCES `game_item_orders` (`id`),
    CONSTRAINT `fk_trade_assignment_machine` FOREIGN KEY (`machine_id`) REFERENCES `machines` (`id`),
    CONSTRAINT `fk_trade_assignment_account` FOREIGN KEY (`game_account_id`) REFERENCES `game_accounts` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='自动交易指派';

CREATE TABLE IF NOT EXISTS `trade_events` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `order_id` INT NOT NULL,
    `assignment_id` VARCHAR(36) NULL,
    `event_type` VARCHAR(64) NOT NULL,
    `from_status` VARCHAR(32) NULL,
    `to_status` VARCHAR(32) NULL,
    `message` VARCHAR(500) NULL,
    `payload` JSON NULL,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    KEY `idx_trade_event_order` (`order_id`, `id`),
    CONSTRAINT `fk_trade_event_order` FOREIGN KEY (`order_id`) REFERENCES `game_item_orders` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='自动交易事件日志';
