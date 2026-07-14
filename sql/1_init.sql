-- 网址统一管理系统 数据库初始化脚本

SET NAMES utf8mb4;

CREATE DATABASE IF NOT EXISTS `auto_login` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE `auto_login`;

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
