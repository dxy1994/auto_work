/*
 Navicat Premium Dump SQL

 Source Server         : localhost_3306
 Source Server Type    : MySQL
 Source Server Version : 80040 (8.0.40)
 Source Host           : localhost:3306
 Source Schema         : auto_login

 Target Server Type    : MySQL
 Target Server Version : 80040 (8.0.40)
 File Encoding         : 65001

 Date: 16/07/2026 14:18:23
*/

SET NAMES utf8mb4;

CREATE DATABASE IF NOT EXISTS `auto_login` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE `auto_login`;

SET FOREIGN_KEY_CHECKS = 0;


-- ----------------------------
-- Table structure for accounts
-- ----------------------------
DROP TABLE IF EXISTS `accounts`;
CREATE TABLE `accounts`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `website_id` int NOT NULL COMMENT '关联网站ID',
  `label` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '账号标签(如：个人/公司)',
  `username` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `password` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT 'AES加密存储',
  `extra_fields` json NULL COMMENT '额外字段(如手机号、邮箱等)',
  `is_default` tinyint(1) NULL DEFAULT 0 COMMENT '是否默认账号',
  `is_active` tinyint(1) NULL DEFAULT 1,
  `created_at` datetime NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `website_id`(`website_id` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 5 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '账号信息表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of accounts
-- ----------------------------
INSERT INTO `accounts` VALUES (1, 3, '1', 'awj810105', 'CYasgwT1Dg7H/lo1zl8uLPZz68KtYCt8rLoAHgP6HM8=', 'null', 1, 1, '2026-07-07 16:03:54', '2026-07-07 16:03:54');
INSERT INTO `accounts` VALUES (2, 1, '1', 'yongchun1225', 'LjdPkFTrgiMthwbhFMEyn37lAcEIwnPboU9TIww/jPs=', 'null', 1, 1, '2026-07-07 16:04:22', '2026-07-07 16:05:11');
INSERT INTO `accounts` VALUES (3, 2, '1', 'yongchun1224', 'Yzdj8uX0fYDtHwCWa/DBBguyHGvQ31fOKCtV2V3AWOk=', 'null', 1, 1, '2026-07-07 16:04:49', '2026-07-07 16:04:49');
INSERT INTO `accounts` VALUES (4, 1, '2', 'khs20020403', '+1piJEauhdvC+omzuk6AE7uyfw6k8DJq4yIgZVq9kyI=', 'null', 0, 1, '2026-07-08 11:39:34', '2026-07-08 11:39:34');

-- ----------------------------
-- Table structure for cookies_store
-- ----------------------------
DROP TABLE IF EXISTS `cookies_store`;
CREATE TABLE `cookies_store`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `website_id` int NOT NULL,
  `account_id` int NOT NULL,
  `cookies` json NOT NULL COMMENT '存储的cookies',
  `expires_at` datetime NULL DEFAULT NULL COMMENT '过期时间',
  `created_at` datetime NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uk_website_account`(`website_id` ASC, `account_id` ASC) USING BTREE,
  INDEX `account_id`(`account_id` ASC) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = 'Cookie持久化表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of cookies_store
-- ----------------------------

-- ----------------------------
-- Table structure for game_accounts
-- ----------------------------
DROP TABLE IF EXISTS `game_accounts`;
CREATE TABLE `game_accounts`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `game_id` int NOT NULL COMMENT '关联游戏ID',
  `region_id` int NULL DEFAULT NULL COMMENT '关联大区ID(NULL表示通用)',
  `machine_id` int NULL DEFAULT NULL COMMENT '绑定机器ID(NULL表示未绑定)',
  `account_name` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '账号名',
  `account_no` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '账号(加密存储)',
  `password` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '密码(加密存储)',
  `nickname` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '游戏内昵称',
  `level` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '账号等级',
  `extra_fields` json NULL COMMENT '额外字段(手机、邮箱等)',
  `status` enum('idle','in_use','locked','disabled') CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT 'idle' COMMENT '账号状态',
  `is_active` tinyint(1) NULL DEFAULT 1,
  `created_at` datetime NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `region_id`(`region_id` ASC) USING BTREE,
  INDEX `idx_game`(`game_id` ASC) USING BTREE,
  INDEX `idx_machine`(`machine_id` ASC) USING BTREE,
  INDEX `idx_status`(`status` ASC) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '游戏账号表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of game_accounts
-- ----------------------------

-- ----------------------------
-- Table structure for game_item_order_details
-- ----------------------------
DROP TABLE IF EXISTS `game_item_order_details`;
CREATE TABLE `game_item_order_details`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `order_id` int NOT NULL COMMENT '关联订单主表ID',
  `item_id` int NOT NULL COMMENT '关联游戏物品ID',
  `item_name` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '物品名称(冗余快照)',
  `item_image` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '物品图片(冗余快照)',
  `quantity` int NOT NULL DEFAULT 1 COMMENT '数量',
  `unit_price` decimal(10, 2) NULL DEFAULT 0.00 COMMENT '单价',
  `subtotal` decimal(12, 2) NULL DEFAULT 0.00 COMMENT '小计金额',
  `purchase_price` decimal(10, 2) NULL DEFAULT NULL COMMENT '进货价(创建时快照)',
  `selling_price` decimal(10, 2) NULL DEFAULT NULL COMMENT '出货价(创建时快照)',
  `status` enum('pending','processing','completed','failed') CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT 'pending' COMMENT '明细状态',
  `remark` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL COMMENT '备注',
  `bundle_name` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '来源套装名称(套装拆分时记录)',
  `created_at` datetime NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `item_id`(`item_id` ASC) USING BTREE,
  INDEX `idx_order`(`order_id` ASC) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '游戏物品订单子表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of game_item_order_details
-- ----------------------------

-- ----------------------------
-- Table structure for game_item_orders
-- ----------------------------
DROP TABLE IF EXISTS `game_item_orders`;
CREATE TABLE `game_item_orders`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `order_no` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '订单编号(全局唯一)',
  `website_id` int NULL DEFAULT NULL COMMENT '来源网站ID',
  `source_order_no` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '平台订单号',
  `game_id` int NOT NULL COMMENT '关联游戏ID',
  `region_id` int NOT NULL COMMENT '关联大区ID',
  `game_account_id` int NULL DEFAULT NULL COMMENT '执行游戏账号ID',
  `buyer_character` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '买家游戏角色名',
  `asset_type` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL DEFAULT 'adena' COMMENT '交付资产类型',
  `asset_amount` decimal(30, 0) NULL DEFAULT NULL COMMENT '交付资产数量',
  `delivery_status` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL DEFAULT 'detected' COMMENT '自动交付状态',
  `assignment_id` varchar(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '当前有效指派ID',
  `row_version` int NOT NULL DEFAULT 0 COMMENT '乐观锁版本',
  `customer_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '客户名称',
  `customer_contact` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '客户联系方式',
  `total_amount` decimal(12, 2) NULL DEFAULT 0.00 COMMENT '订单总金额',
  `status` enum('pending','assigned','processing','completed','cancelled') CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT 'pending' COMMENT '订单状态: pending=待分配, assigned=已分配, processing=处理中, completed=已完成, cancelled=已取消',
  `assigned_machine_id` int NULL DEFAULT NULL COMMENT '分配的机器ID',
  `assigned_at` datetime NULL DEFAULT NULL COMMENT '分配时间',
  `completed_at` datetime NULL DEFAULT NULL COMMENT '完成时间',
  `game_delivered_at` datetime NULL DEFAULT NULL COMMENT '游戏交付时间',
  `website_confirmed_at` datetime NULL DEFAULT NULL COMMENT '网站确认时间',
  `last_error_code` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '最后错误编码',
  `last_error_message` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '最后错误描述',
  `remark` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL COMMENT '备注',
  `created_at` datetime NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `platform_order_time` datetime NULL DEFAULT NULL COMMENT '平台原始下单时间',
  `platform_price` decimal(12, 2) NULL DEFAULT NULL COMMENT '平台售价(원)',
  `platform_item_type` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '平台物品分类(게임머니/아이템/계정)',
  `product_title` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '平台商品标题',
  `trade_item_name` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '实际交易物品名(从标题[]解析,用于匹配子订单)',
  `quantity` int NULL DEFAULT 1 COMMENT '上架数量',
  `sale_quantity` int NULL DEFAULT 1 COMMENT '已售数量',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uk_order_no`(`order_no` ASC) USING BTREE,
  UNIQUE INDEX `uk_source_order`(`website_id` ASC, `source_order_no` ASC) USING BTREE,
  INDEX `region_id`(`region_id` ASC) USING BTREE,
  INDEX `idx_status`(`status` ASC) USING BTREE,
  INDEX `idx_game`(`game_id` ASC) USING BTREE,
  INDEX `idx_machine`(`assigned_machine_id` ASC) USING BTREE,
  INDEX `idx_delivery_status`(`delivery_status` ASC) USING BTREE,
  INDEX `idx_assignment_id`(`assignment_id` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 6 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '游戏物品订单主表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of game_item_orders
-- ----------------------------

-- ----------------------------
-- Table structure for game_items
-- ----------------------------
DROP TABLE IF EXISTS `game_items`;
CREATE TABLE `game_items`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `game_id` int NOT NULL COMMENT '关联游戏ID',
  `name` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '物品名称',
  `code` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '物品编码',
  `image` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '商品图片URL',
  `is_bundle` tinyint(1) NULL DEFAULT 0 COMMENT '是否为套装(1=套装, 0=单品)',
  `category` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '物品分类',
  `price` decimal(10, 2) NULL DEFAULT 0.00 COMMENT '参考价格',
  `position` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '位置坐标（如X:100,Y:200）',
  `remark` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL COMMENT '备注',
  `sort_order` int NULL DEFAULT 0 COMMENT '排序',
  `is_active` tinyint(1) NULL DEFAULT 1,
  `created_at` datetime NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uk_game_item`(`game_id` ASC, `code` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 2 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '游戏物品表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Table structure for bundle_items
-- ----------------------------
DROP TABLE IF EXISTS `bundle_items`;
CREATE TABLE `bundle_items`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `bundle_id` int NOT NULL COMMENT '套装ID',
  `item_id` int NOT NULL COMMENT '物品ID',
  `sort_order` int NULL DEFAULT 0 COMMENT '排序',
  `created_at` datetime NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uk_bundle_item`(`bundle_id` ASC, `item_id` ASC) USING BTREE,
  INDEX `idx_item`(`item_id` ASC) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '套装物品关联表（多对多）' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of game_items
-- ----------------------------
INSERT INTO `game_items` VALUES (1, 1, '游戏币', '게임머니', '', 0, 'coin', 0.00, NULL, '', 0, 1, '2026-07-15 11:11:06', '2026-07-15 11:11:06');

-- ----------------------------
-- Table structure for game_region_items
-- ----------------------------
DROP TABLE IF EXISTS `game_region_items`;
CREATE TABLE `game_region_items`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `game_id` int NOT NULL COMMENT '关联游戏ID',
  `region_id` int NOT NULL COMMENT '关联大区ID',
  `item_id` int NOT NULL COMMENT '关联物品ID',
  `stock` int NOT NULL DEFAULT 0 COMMENT '库存数量',
  `purchase_price` decimal(10, 2) NOT NULL DEFAULT 0.00 COMMENT '当前进货价',
  `selling_price` decimal(10, 2) NOT NULL DEFAULT 0.00 COMMENT '当前出货价',
  `min_selling_price` decimal(10, 2) NOT NULL DEFAULT 0.00 COMMENT '最小出货价',
  `max_selling_price` decimal(10, 2) NOT NULL DEFAULT 0.00 COMMENT '最大出货价',
  `max_fluctuation` decimal(10, 2) NULL DEFAULT NULL COMMENT '单次出货最大波动(固定值)',
  `max_fluctuation_rate` decimal(5, 2) NULL DEFAULT NULL COMMENT '单次出货最大波动(百分比)',
  `is_active` tinyint(1) NULL DEFAULT 1,
  `created_at` datetime NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uk_region_item`(`region_id` ASC, `item_id` ASC) USING BTREE,
  INDEX `idx_game`(`game_id` ASC) USING BTREE,
  INDEX `idx_region`(`region_id` ASC) USING BTREE,
  INDEX `idx_item`(`item_id` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 30 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '大区物品库存表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of game_region_items
-- ----------------------------
INSERT INTO `game_region_items` VALUES (1, 1, 1, 1, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-15 11:27:07', '2026-07-15 11:27:07');
INSERT INTO `game_region_items` VALUES (2, 1, 2, 1, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-15 11:27:50', '2026-07-15 11:27:50');
INSERT INTO `game_region_items` VALUES (3, 1, 4, 1, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-15 11:41:29', '2026-07-15 11:41:29');
INSERT INTO `game_region_items` VALUES (4, 1, 5, 1, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-15 11:42:56', '2026-07-15 11:42:56');
INSERT INTO `game_region_items` VALUES (5, 1, 6, 1, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-15 11:43:04', '2026-07-15 11:43:04');
INSERT INTO `game_region_items` VALUES (6, 1, 7, 1, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-15 11:43:12', '2026-07-15 11:43:12');
INSERT INTO `game_region_items` VALUES (7, 1, 8, 1, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-15 11:43:20', '2026-07-15 11:43:20');
INSERT INTO `game_region_items` VALUES (8, 1, 9, 1, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-15 11:43:29', '2026-07-15 11:43:29');
INSERT INTO `game_region_items` VALUES (9, 1, 10, 1, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-15 11:43:43', '2026-07-15 11:43:43');
INSERT INTO `game_region_items` VALUES (10, 1, 11, 1, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-15 11:43:50', '2026-07-15 11:43:50');
INSERT INTO `game_region_items` VALUES (11, 1, 12, 1, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-15 11:43:58', '2026-07-15 11:43:58');
INSERT INTO `game_region_items` VALUES (12, 1, 13, 1, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-15 11:44:06', '2026-07-15 11:44:06');
INSERT INTO `game_region_items` VALUES (13, 1, 14, 1, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-15 11:44:15', '2026-07-15 11:44:15');
INSERT INTO `game_region_items` VALUES (14, 1, 15, 1, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-15 11:44:25', '2026-07-15 11:44:25');
INSERT INTO `game_region_items` VALUES (15, 1, 16, 1, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-15 11:44:33', '2026-07-15 11:44:33');
INSERT INTO `game_region_items` VALUES (16, 1, 17, 1, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-15 11:44:42', '2026-07-15 11:44:42');
INSERT INTO `game_region_items` VALUES (17, 1, 18, 1, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-15 11:44:50', '2026-07-15 11:44:50');
INSERT INTO `game_region_items` VALUES (18, 1, 19, 1, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-15 11:44:58', '2026-07-15 11:44:58');
INSERT INTO `game_region_items` VALUES (19, 1, 20, 1, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-15 11:45:07', '2026-07-15 11:45:07');
INSERT INTO `game_region_items` VALUES (20, 1, 21, 1, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-15 11:45:15', '2026-07-15 11:45:15');
INSERT INTO `game_region_items` VALUES (21, 1, 22, 1, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-15 11:45:24', '2026-07-15 11:45:24');
INSERT INTO `game_region_items` VALUES (22, 1, 23, 1, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-15 11:45:32', '2026-07-15 11:45:32');
INSERT INTO `game_region_items` VALUES (23, 1, 24, 1, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-15 11:45:39', '2026-07-15 11:45:39');
INSERT INTO `game_region_items` VALUES (24, 1, 25, 1, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-15 11:45:46', '2026-07-15 11:45:46');
INSERT INTO `game_region_items` VALUES (25, 1, 26, 1, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-15 11:45:53', '2026-07-15 11:45:53');
INSERT INTO `game_region_items` VALUES (26, 1, 27, 1, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-15 11:46:01', '2026-07-15 11:46:01');
INSERT INTO `game_region_items` VALUES (27, 1, 28, 1, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-15 11:46:08', '2026-07-15 11:46:08');
INSERT INTO `game_region_items` VALUES (28, 1, 29, 1, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-15 11:46:15', '2026-07-15 11:46:15');
INSERT INTO `game_region_items` VALUES (29, 1, 30, 1, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-15 11:51:12', '2026-07-15 11:51:12');

-- ----------------------------
-- Table structure for game_regions
-- ----------------------------
DROP TABLE IF EXISTS `game_regions`;
CREATE TABLE `game_regions`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `game_id` int NOT NULL COMMENT '关联游戏ID',
  `name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '大区名称',
  `code` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '大区编码',
  `sort_order` int NULL DEFAULT 0 COMMENT '排序',
  `is_active` tinyint(1) NULL DEFAULT 1,
  `created_at` datetime NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uk_game_region`(`game_id` ASC, `code` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 31 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '游戏大区表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of game_regions
-- ----------------------------
INSERT INTO `game_regions` VALUES (1, 1, '太陽神阿波羅', '데포로쥬', 1, 1, '2026-07-15 11:27:07', '2026-07-15 11:27:30');
INSERT INTO `game_regions` VALUES (2, 1, '愛神邱比特', '켄라우헬', 2, 1, '2026-07-15 11:27:50', '2026-07-15 11:28:16');
INSERT INTO `game_regions` VALUES (4, 1, '勝利女神雅典娜', '질리언', 3, 1, '2026-07-15 11:41:28', '2026-07-15 11:42:38');
INSERT INTO `game_regions` VALUES (5, 1, '美神維納斯', '이실로테', 4, 1, '2026-07-15 11:42:56', '2026-07-15 11:42:56');
INSERT INTO `game_regions` VALUES (6, 1, '天神宙斯', '조우', 5, 1, '2026-07-15 11:43:04', '2026-07-15 11:43:04');
INSERT INTO `game_regions` VALUES (7, 1, '天后海拉', '하딘', 6, 1, '2026-07-15 11:43:12', '2026-07-15 11:43:12');
INSERT INTO `game_regions` VALUES (8, 1, '戰神馬爾斯', '케레니스', 7, 1, '2026-07-15 11:43:20', '2026-07-15 11:43:20');
INSERT INTO `game_regions` VALUES (9, 1, '月亮女神阿缇蜜斯', '오웬', 8, 1, '2026-07-15 11:43:29', '2026-07-15 11:43:29');
INSERT INTO `game_regions` VALUES (10, 1, '海神波塞冬', '크리스터', 9, 1, '2026-07-15 11:43:43', '2026-07-15 11:43:43');
INSERT INTO `game_regions` VALUES (11, 1, '水蛇許德拉', '아인하사드', 10, 1, '2026-07-15 11:43:50', '2026-07-15 11:43:50');
INSERT INTO `game_regions` VALUES (12, 1, '冥王哈迪斯', '아툰', 11, 1, '2026-07-15 11:43:58', '2026-07-15 11:43:58');
INSERT INTO `game_regions` VALUES (13, 1, '火神赫發斯特斯', '가드리아', 12, 1, '2026-07-15 11:44:06', '2026-07-15 11:44:06');
INSERT INTO `game_regions` VALUES (14, 1, '收穫女神帝蜜特', '군터', 13, 1, '2026-07-15 11:44:15', '2026-07-15 11:44:15');
INSERT INTO `game_regions` VALUES (15, 1, '蛇髮女美杜沙', '아스테어', 14, 1, '2026-07-15 11:44:25', '2026-07-15 11:44:25');
INSERT INTO `game_regions` VALUES (16, 1, '半人馬涅索斯', '듀크데필', 15, 1, '2026-07-15 11:44:33', '2026-07-15 11:44:33');
INSERT INTO `game_regions` VALUES (17, 1, '牛人彌諾陶洛斯1', '발센', 16, 1, '2026-07-15 11:44:42', '2026-07-15 11:44:42');
INSERT INTO `game_regions` VALUES (18, 1, '俄雷恩', '어레인', 17, 1, '2026-07-15 11:44:50', '2026-07-15 11:44:50');
INSERT INTO `game_regions` VALUES (19, 1, '獨眼巨人庫克羅普', '캐스톨', 18, 1, '2026-07-15 11:44:58', '2026-07-15 11:44:58');
INSERT INTO `game_regions` VALUES (20, 1, '獅子涅墨亞', '세바스챤', 19, 1, '2026-07-15 11:45:07', '2026-07-15 11:45:07');
INSERT INTO `game_regions` VALUES (21, 1, '飛馬珀伽索斯', '데컨', 20, 1, '2026-07-15 11:45:15', '2026-07-15 11:45:15');
INSERT INTO `game_regions` VALUES (22, 1, '公牛克里特', '파아그리오', 21, 1, '2026-07-15 11:45:24', '2026-07-15 11:45:24');
INSERT INTO `game_regions` VALUES (23, 1, '女妖塞壬', '에바', 22, 1, '2026-07-15 11:45:32', '2026-07-15 11:45:32');
INSERT INTO `game_regions` VALUES (24, 1, '巨龍拉多', '사이하', 23, 1, '2026-07-15 11:45:39', '2026-07-15 11:45:39');
INSERT INTO `game_regions` VALUES (25, 1, '百眼怪阿爾戈斯', '마프르', 24, 1, '2026-07-15 11:45:46', '2026-07-15 11:45:46');
INSERT INTO `game_regions` VALUES (26, 1, '大地之神蓋亞', '린델', 25, 1, '2026-07-15 11:45:53', '2026-07-15 11:45:53');
INSERT INTO `game_regions` VALUES (27, 1, '牛人彌諾陶洛斯2', '하이네', 26, 1, '2026-07-15 11:46:01', '2026-07-15 11:46:01');
INSERT INTO `game_regions` VALUES (28, 1, '泰坦女神瑞亞', '로엔그린', 27, 1, '2026-07-15 11:46:08', '2026-07-15 11:46:08');
INSERT INTO `game_regions` VALUES (29, 1, '地狱犬刻耳柏洛斯', '발라카스', 28, 1, '2026-07-15 11:46:15', '2026-07-15 11:46:15');
INSERT INTO `game_regions` VALUES (30, 1, '獨眼巨人庫克羅普斯', '오렌', 29, 1, '2026-07-15 11:51:12', '2026-07-15 11:51:12');

-- ----------------------------
-- Table structure for game_scripts
-- ----------------------------
DROP TABLE IF EXISTS `game_scripts`;
CREATE TABLE `game_scripts`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `game_id` int NOT NULL COMMENT '关联游戏ID',
  `title` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '话术标题',
  `content` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '话术内容',
  `category` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '话术分类(如：招呼、促单、售后)',
  `sort_order` int NULL DEFAULT 0 COMMENT '排序',
  `is_active` tinyint(1) NULL DEFAULT 1,
  `created_at` datetime NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_game`(`game_id` ASC) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '游戏话术表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of game_scripts
-- ----------------------------

-- ----------------------------
-- Table structure for games
-- ----------------------------
DROP TABLE IF EXISTS `games`;
CREATE TABLE `games`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '游戏名称',
  `code` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '游戏编码(唯一标识)',
  `icon` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '游戏图标URL',
  `platform` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '平台(PC/手游/主机)',
  `remark` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL COMMENT '备注',
  `sort_order` int NULL DEFAULT 0 COMMENT '排序',
  `is_active` tinyint(1) NULL DEFAULT 1,
  `created_at` datetime NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uk_code`(`code` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 3 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '游戏表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of games
-- ----------------------------
INSERT INTO `games` VALUES (1, '天堂经典版', '리니지클래식', '', 'PC', '', 0, 1, '2026-07-15 11:01:45', '2026-07-15 11:01:45');
INSERT INTO `games` VALUES (2, '暗黑2:休闲版', '디아블로2:레저렉션', '', 'PC', '', 1, 1, '2026-07-15 11:02:42', '2026-07-15 11:02:42');

-- ----------------------------
-- Table structure for machine_games
-- ----------------------------
DROP TABLE IF EXISTS `machine_games`;
CREATE TABLE `machine_games`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `machine_id` int NOT NULL COMMENT '关联机器ID',
  `game_id` int NOT NULL COMMENT '关联游戏ID',
  `priority` int NULL DEFAULT 0 COMMENT '优先级(数字越大优先级越高)',
  `max_concurrent` int NULL DEFAULT 1 COMMENT '最大并发订单数',
  `is_active` tinyint(1) NULL DEFAULT 1,
  `created_at` datetime NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uk_machine_game`(`machine_id` ASC, `game_id` ASC) USING BTREE,
  INDEX `game_id`(`game_id` ASC) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '机器关联游戏表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of machine_games
-- ----------------------------

-- ----------------------------
-- Table structure for machines
-- ----------------------------
DROP TABLE IF EXISTS `machines`;
CREATE TABLE `machines`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `mac_address` varchar(17) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT 'MAC地址(唯一标识, 格式: AA:BB:CC:DD:EE:FF)',
  `hostname` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '机器主机名',
  `ip_address` varchar(45) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT 'IP地址',
  `name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '机器别名/标签',
  `os_info` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '操作系统信息',
  `status` enum('online','offline','busy','disabled') CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT 'offline' COMMENT '机器状态',
  `last_heartbeat` datetime NULL DEFAULT NULL COMMENT '最后心跳时间',
  `remark` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL COMMENT '备注',
  `is_active` tinyint(1) NULL DEFAULT 1,
  `created_at` datetime NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uk_mac`(`mac_address` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 2 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '机器表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of machines
-- ----------------------------
INSERT INTO `machines` VALUES (1, 'A8:2B:DD:1B:73:5A', '白金之星', '10.64.0.2', NULL, 'Windows 11', 'online', '2026-07-16 14:03:19', NULL, 1, '2026-07-15 10:51:49', '2026-07-15 10:51:49');

-- ----------------------------
-- Table structure for region_scripts
-- ----------------------------
DROP TABLE IF EXISTS `region_scripts`;
CREATE TABLE `region_scripts`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `region_id` int NOT NULL COMMENT '关联大区ID',
  `game_script_id` int NULL DEFAULT NULL COMMENT '关联游戏话术ID(NULL表示独立话术)',
  `title` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '话术标题',
  `content` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '话术内容',
  `position_image` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '位置图片URL',
  `category` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '话术分类',
  `sort_order` int NULL DEFAULT 0 COMMENT '排序',
  `is_active` tinyint(1) NULL DEFAULT 1,
  `created_at` datetime NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `game_script_id`(`game_script_id` ASC) USING BTREE,
  INDEX `idx_region`(`region_id` ASC) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '大区话术表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of region_scripts
-- ----------------------------

-- ----------------------------
-- Table structure for trade_assignments
-- ----------------------------
DROP TABLE IF EXISTS `trade_assignments`;
CREATE TABLE `trade_assignments`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `assignment_id` varchar(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `order_id` int NOT NULL,
  `machine_id` int NOT NULL,
  `game_account_id` int NOT NULL,
  `status` varchar(24) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `token_hash` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `lease_expires_at` datetime NOT NULL,
  `reject_reason` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL,
  `accepted_at` datetime NULL DEFAULT NULL,
  `started_at` datetime NULL DEFAULT NULL,
  `finished_at` datetime NULL DEFAULT NULL,
  `created_at` datetime NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uk_assignment_id`(`assignment_id` ASC) USING BTREE,
  INDEX `idx_assignment_order_status`(`order_id` ASC, `status` ASC) USING BTREE,
  INDEX `machine_id`(`machine_id` ASC) USING BTREE,
  INDEX `game_account_id`(`game_account_id` ASC) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '自动交易指派' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of trade_assignments
-- ----------------------------

-- ----------------------------
-- Table structure for trade_events
-- ----------------------------
DROP TABLE IF EXISTS `trade_events`;
CREATE TABLE `trade_events`  (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `order_id` int NOT NULL,
  `assignment_id` varchar(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL,
  `event_type` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `from_status` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL,
  `to_status` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL,
  `message` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL,
  `payload` json NULL,
  `created_at` datetime NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_trade_event_order`(`order_id` ASC, `id` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 3 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '自动交易事件日志' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of trade_events
-- ----------------------------

-- ----------------------------
-- Table structure for website_schedules
-- ----------------------------
DROP TABLE IF EXISTS `website_schedules`;
CREATE TABLE `website_schedules`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `account_id` int NOT NULL COMMENT '关联账号ID',
  `name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '子功能名',
  `code` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '编码',
  `refresh_interval` int NULL DEFAULT -1 COMMENT '刷新频率(秒)，-1表示无需刷新',
  `schedule_type` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT 'none' COMMENT '定时类型: none/once/scheduled',
  `schedule_time` datetime NULL DEFAULT NULL COMMENT '执行时间(schedule_type=once时使用)',
  `schedule_cron` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '执行间隔(秒)(schedule_type=scheduled时使用)',
  `alert_audio_path` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '提醒音频文件本地路径',
  `is_enabled` tinyint(1) NULL DEFAULT 1 COMMENT '是否启用',
  `created_at` datetime NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uk_account_code`(`account_id` ASC, `code` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 2 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '账号子功能配置表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of website_schedules
-- ----------------------------
INSERT INTO `website_schedules` VALUES (1, 1, '刷新上架货品', 'refresh_up_goods', -1, 'scheduled', NULL, '40', 'uploads/audio/81035b19e00b414ca41b31a0d925533b.mp3', 1, '2026-07-07 16:36:04', '2026-07-07 17:07:39');

-- ----------------------------
-- Table structure for websites
-- ----------------------------
DROP TABLE IF EXISTS `websites`;
CREATE TABLE `websites`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '网站名称',
  `url` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '登录页URL',
  `icon` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '网站图标URL',
  `category` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '分类(如：办公/社交/开发)',
  `login_type` enum('form','captcha','oauth') CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT 'form' COMMENT '登录类型',
  `login_config` json NULL COMMENT '登录配置(表单选择器、字段映射等)',
  `remark` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL COMMENT '备注',
  `sort_order` int NULL DEFAULT 0 COMMENT '排序',
  `is_active` tinyint(1) NULL DEFAULT 1,
  `created_at` datetime NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 4 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '网站信息表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of websites
-- ----------------------------
INSERT INTO `websites` VALUES (1, 'mania', 'https://www.itemmania.com/portal/user/p_login_form.html', '', '', 'form', '{\"success_url\": \"\", \"submit_selector\": \"#login_before button[type=submit]\", \"captcha_selector\": \"\", \"password_selector\": \"#user_password\", \"username_selector\": \"#user_id\", \"captcha_input_selector\": \"\"}', '', 1, 1, '2026-07-07 15:57:22', '2026-07-08 12:18:07');
INSERT INTO `websites` VALUES (2, 'arotem', 'https://www.barotem.com/auth/login', '', '', 'captcha', '{\"success_url\": \"\", \"submit_selector\": \".login_btn\", \"captcha_selector\": \"\", \"password_selector\": \"#memberPass\", \"username_selector\": \"#memberId\", \"captcha_input_selector\": \"\"}', '', 2, 1, '2026-07-07 16:00:55', '2026-07-15 10:58:16');
INSERT INTO `websites` VALUES (3, 'itemBay', 'https://www.itembay.com/login/loginAdult', '', '', 'form', '{\"success_url\": \"\", \"submit_selector\": \"div.btn_login\", \"captcha_selector\": \"\", \"password_selector\": \"#txtPassword\", \"username_selector\": \"#txtMemberID\", \"captcha_input_selector\": \"\"}', '', 3, 1, '2026-07-07 16:03:08', '2026-07-15 10:58:16');

SET FOREIGN_KEY_CHECKS = 1;
