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

 Date: 19/07/2026 14:47:26
*/

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for accounts
-- ----------------------------
DROP TABLE IF EXISTS `platform_accounts`;
CREATE TABLE `platform_accounts`  (
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
INSERT INTO `platform_accounts` VALUES (1, 3, '1', 'awj810105', 'CYasgwT1Dg7H/lo1zl8uLPZz68KtYCt8rLoAHgP6HM8=', 'null', 1, 1, '2026-07-07 16:03:54', '2026-07-07 16:03:54');
INSERT INTO `platform_accounts` VALUES (2, 1, '1', 'yongchun1225', 'LjdPkFTrgiMthwbhFMEyn37lAcEIwnPboU9TIww/jPs=', 'null', 1, 1, '2026-07-07 16:04:22', '2026-07-07 16:05:11');
INSERT INTO `platform_accounts` VALUES (3, 2, '1', 'yongchun1224', 'Yzdj8uX0fYDtHwCWa/DBBguyHGvQ31fOKCtV2V3AWOk=', 'null', 1, 1, '2026-07-07 16:04:49', '2026-07-07 16:04:49');
INSERT INTO `platform_accounts` VALUES (4, 1, '2', 'khs20020403', '+1piJEauhdvC+omzuk6AE7uyfw6k8DJq4yIgZVq9kyI=', 'null', 0, 1, '2026-07-08 11:39:34', '2026-07-08 11:39:34');

-- ----------------------------
-- Table structure for bundle_items
-- ----------------------------
DROP TABLE IF EXISTS `item_bundle_relations`;
CREATE TABLE `item_bundle_relations`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `bundle_id` int NOT NULL COMMENT '套装ID',
  `item_id` int NOT NULL COMMENT '物品ID',
  `quantity` int NOT NULL DEFAULT 1 COMMENT '数量',
  `sort_order` int NULL DEFAULT 0 COMMENT '排序',
  `created_at` datetime NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uk_bundle_item`(`bundle_id` ASC, `item_id` ASC) USING BTREE,
  INDEX `idx_item`(`item_id` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 10 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '套装物品关联表（多对多）' ROW_FORMAT = Dynamic;

-- ----------------------------
-- Records of bundle_items
-- ----------------------------
INSERT INTO `item_bundle_relations` VALUES (4, 3, 34, 1, 0, '2026-07-17 12:59:14');
INSERT INTO `item_bundle_relations` VALUES (5, 3, 9, 1, 0, '2026-07-17 12:59:28');
INSERT INTO `item_bundle_relations` VALUES (6, 3, 33, 1, 0, '2026-07-17 13:06:57');
INSERT INTO `item_bundle_relations` VALUES (7, 37, 33, 1, 0, '2026-07-17 13:07:16');
INSERT INTO `item_bundle_relations` VALUES (8, 37, 26, 1, 0, '2026-07-17 13:07:27');
INSERT INTO `item_bundle_relations` VALUES (9, 37, 27, 1, 0, '2026-07-17 13:08:11');

-- 迁移：为已有数据库添加数量字段（如果表已存在）
-- ALTER TABLE `item_bundle_relations` ADD COLUMN `quantity` INT NOT NULL DEFAULT 1 COMMENT '数量' AFTER `item_id`;

-- ----------------------------
-- Table structure for cookies_store
-- ----------------------------
DROP TABLE IF EXISTS `platform_cookies`;
CREATE TABLE `platform_cookies`  (
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
) ENGINE = InnoDB AUTO_INCREMENT = 1 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = 'Cookie持久化表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of cookies_store
-- ----------------------------

-- ----------------------------
-- Table structure for game_account_regions
-- ----------------------------
DROP TABLE IF EXISTS `game_account_regions`;
CREATE TABLE `game_account_regions`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `game_account_id` int NOT NULL COMMENT '关联游戏账号ID',
  `region_id` int NOT NULL COMMENT '关联大区ID',
  `is_active` tinyint(1) NULL DEFAULT 1,
  `created_at` datetime NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uk_account_region`(`game_account_id` ASC, `region_id` ASC) USING BTREE,
  INDEX `idx_region_id`(`region_id` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 1 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '游戏账号-大区关联表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of game_account_regions
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
) ENGINE = InnoDB AUTO_INCREMENT = 1 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '游戏账号表' ROW_FORMAT = DYNAMIC;

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
) ENGINE = InnoDB AUTO_INCREMENT = 1 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '游戏物品订单子表' ROW_FORMAT = DYNAMIC;

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
) ENGINE = InnoDB AUTO_INCREMENT = 22 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '游戏物品订单主表' ROW_FORMAT = DYNAMIC;

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
  `position` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT 'ä½ç½®åæ ‡ï¼ˆå¦‚X:100,Y:200ï¼‰',
  `remark` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL COMMENT '备注',
  `sort_order` int NULL DEFAULT 0 COMMENT '排序',
  `is_active` tinyint(1) NULL DEFAULT 1,
  `created_at` datetime NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uk_game_item`(`game_id` ASC, `code` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 38 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '游戏物品表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of game_items
-- ----------------------------
INSERT INTO `game_items` VALUES (1, 1, '游戏币', '게임머니', '', 0, '游戏币', 0.00, NULL, '', 0, 1, '2026-07-15 11:11:06', '2026-07-15 11:11:06');
INSERT INTO `game_items` VALUES (3, 2, '수수룬셋', '수수룬셋', '', 1, '物品', 0.00, NULL, '', 0, 1, '2026-07-17 11:17:48', '2026-07-17 11:17:48');
INSERT INTO `game_items` VALUES (4, 2, '艾尔', '엘룬', '', 0, '物品', 0.00, '1,1', '', 0, 1, '2026-07-17 11:27:58', '2026-07-17 12:27:23');
INSERT INTO `game_items` VALUES (5, 2, '艾德', '엘드룬', '', 0, '物品', 0.00, '1,2', '', 0, 1, '2026-07-17 12:14:09', '2026-07-17 12:27:23');
INSERT INTO `game_items` VALUES (6, 2, '特尔', '티르룬', '', 0, '物品', 0.00, '1,3', '', 0, 1, '2026-07-17 12:18:35', '2026-07-17 12:27:23');
INSERT INTO `game_items` VALUES (7, 2, '那夫', '네프룬', '', 0, '物品', 0.00, '1,4', '', 4, 1, '2026-07-17 11:17:48', '2026-07-17 12:27:23');
INSERT INTO `game_items` VALUES (8, 2, '爱斯', '에드룬', '', 0, '物品', 0.00, '1,5', '', 5, 1, '2026-07-17 11:17:48', '2026-07-17 12:27:23');
INSERT INTO `game_items` VALUES (9, 2, '伊司', '아이드룬', '', 0, '物品', 0.00, '1,6', '', 6, 1, '2026-07-17 11:17:48', '2026-07-17 12:27:23');
INSERT INTO `game_items` VALUES (10, 2, '塔尔', '탈룬', '', 0, '物品', 0.00, '1,7', '', 7, 1, '2026-07-17 11:17:48', '2026-07-17 12:27:23');
INSERT INTO `game_items` VALUES (11, 2, '拉尔', '랄룬', '', 0, '物品', 0.00, '1,8', '', 8, 1, '2026-07-17 12:25:54', '2026-07-17 12:27:32');
INSERT INTO `game_items` VALUES (12, 2, '欧特', '오르트룬', '', 0, '物品', 0.00, '2,1', '', 9, 1, '2026-07-17 12:26:19', '2026-07-17 12:27:32');
INSERT INTO `game_items` VALUES (13, 2, '书尔', '툴룬', '', 0, '物品', 0.00, '2,2', '', 10, 1, '2026-07-17 12:38:09', '2026-07-17 12:50:20');
INSERT INTO `game_items` VALUES (14, 2, '安姆', '암룬', '', 0, '物品', 0.00, '2,3', '', 11, 1, '2026-07-17 12:38:27', '2026-07-17 12:50:20');
INSERT INTO `game_items` VALUES (15, 2, '索尔', '솔룬', '', 0, '物品', 0.00, '2,4', '', 12, 1, '2026-07-17 12:40:34', '2026-07-17 12:50:20');
INSERT INTO `game_items` VALUES (16, 2, '夏', '샤엘룬', '', 0, '物品', 0.00, '2,5', '', 13, 1, '2026-07-17 12:41:10', '2026-07-17 12:50:20');
INSERT INTO `game_items` VALUES (17, 2, '多尔', '돌룬', '', 0, '物品', 0.00, '2,6', '', 14, 1, '2026-07-17 12:41:44', '2026-07-17 12:50:20');
INSERT INTO `game_items` VALUES (18, 2, '海尔', '헬룬', '', 0, '物品', 0.00, '2,7', '', 15, 1, '2026-07-17 12:43:16', '2026-07-17 12:50:20');
INSERT INTO `game_items` VALUES (19, 2, '埃欧', '이오룬', '', 0, '物品', 0.00, '2,8', '', 16, 1, '2026-07-17 12:43:38', '2026-07-17 12:50:20');
INSERT INTO `game_items` VALUES (20, 2, '卢姆', '룸룬', '', 0, '物品', 0.00, '3,1', '', 17, 1, '2026-07-17 12:43:58', '2026-07-17 12:50:20');
INSERT INTO `game_items` VALUES (21, 2, '科', '코룬', '', 0, '物品', 0.00, '3,2', '', 18, 1, '2026-07-17 12:44:18', '2026-07-17 12:50:20');
INSERT INTO `game_items` VALUES (22, 2, '法尔', '팔룬', '', 0, '物品', 0.00, '3,3', '', 19, 1, '2026-07-17 12:44:42', '2026-07-17 12:50:20');
INSERT INTO `game_items` VALUES (23, 2, '蓝姆', '렘룬', '', 0, '物品', 0.00, '3,4', '', 20, 1, '2026-07-17 12:45:00', '2026-07-17 12:50:20');
INSERT INTO `game_items` VALUES (24, 2, '普尔', '풀룬', '', 0, '物品', 0.00, '3,5', '', 21, 1, '2026-07-17 12:45:46', '2026-07-17 12:50:20');
INSERT INTO `game_items` VALUES (25, 2, '乌姆', '우움룬', '', 0, '物品', 0.00, '3,6', '', 22, 1, '2026-07-17 12:45:59', '2026-07-17 12:50:20');
INSERT INTO `game_items` VALUES (26, 2, '马尔', '말룬', '', 0, '物品', 0.00, '3,7', '', 23, 1, '2026-07-17 12:46:14', '2026-07-17 12:50:20');
INSERT INTO `game_items` VALUES (27, 2, '伊司特', '이스트룬', '', 0, '物品', 0.00, '3,8', '', 24, 1, '2026-07-17 12:46:27', '2026-07-17 12:50:20');
INSERT INTO `game_items` VALUES (28, 2, '古尔', '굴룬', '', 0, '物品', 0.00, '4,1', '', 25, 1, '2026-07-17 12:46:46', '2026-07-17 12:50:20');
INSERT INTO `game_items` VALUES (29, 2, '伐克斯', '벡스룬', '', 0, '物品', 0.00, '4,2', '', 26, 1, '2026-07-17 12:47:02', '2026-07-17 12:50:20');
INSERT INTO `game_items` VALUES (30, 2, '欧姆', '옴룬', '', 0, '物品', 0.00, '4,3', '', 27, 1, '2026-07-17 12:47:19', '2026-07-17 12:50:20');
INSERT INTO `game_items` VALUES (31, 2, '罗', '로룬', '', 0, '物品', 0.00, '4,4', '', 28, 1, '2026-07-17 12:47:35', '2026-07-17 12:50:20');
INSERT INTO `game_items` VALUES (32, 2, '瑟', '서룬', '', 0, '物品', 0.00, '4,5', '', 29, 1, '2026-07-17 12:47:48', '2026-07-17 12:50:20');
INSERT INTO `game_items` VALUES (33, 2, '贝', '베르룬', '', 0, '物品', 0.00, '4,6', '', 30, 1, '2026-07-17 12:48:01', '2026-07-17 12:50:20');
INSERT INTO `game_items` VALUES (34, 2, '乔', '자룬', '', 0, '物品', 0.00, '4,7', '', 31, 1, '2026-07-17 12:48:20', '2026-07-17 12:50:20');
INSERT INTO `game_items` VALUES (35, 2, '查姆', '참룬', '', 0, '物品', 0.00, '4,8', '', 32, 1, '2026-07-17 12:48:37', '2026-07-17 12:50:20');
INSERT INTO `game_items` VALUES (36, 2, '萨德', '조드룬', '', 0, '物品', 0.00, '5,1', '', 33, 1, '2026-07-17 12:48:56', '2026-07-17 12:50:20');
INSERT INTO `game_items` VALUES (37, 2, '무공룬셋', '무공룬셋', '', 1, '物品', 0.00, '', '', 1, 1, '2026-07-17 11:17:48', '2026-07-17 11:17:48');

-- ----------------------------
-- Table structure for game_region_items
-- ----------------------------
DROP TABLE IF EXISTS `game_region_inventory`;
CREATE TABLE `game_region_inventory`  (
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
) ENGINE = InnoDB AUTO_INCREMENT = 282 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '大区物品库存表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of game_region_items
-- ----------------------------
INSERT INTO `game_region_inventory` VALUES (1, 1, 1, 1, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-15 11:27:07', '2026-07-15 11:27:07');
INSERT INTO `game_region_inventory` VALUES (2, 1, 2, 1, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-15 11:27:50', '2026-07-15 11:27:50');
INSERT INTO `game_region_inventory` VALUES (3, 1, 4, 1, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-15 11:41:29', '2026-07-15 11:41:29');
INSERT INTO `game_region_inventory` VALUES (4, 1, 5, 1, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-15 11:42:56', '2026-07-15 11:42:56');
INSERT INTO `game_region_inventory` VALUES (5, 1, 6, 1, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-15 11:43:04', '2026-07-15 11:43:04');
INSERT INTO `game_region_inventory` VALUES (6, 1, 7, 1, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-15 11:43:12', '2026-07-15 11:43:12');
INSERT INTO `game_region_inventory` VALUES (7, 1, 8, 1, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-15 11:43:20', '2026-07-15 11:43:20');
INSERT INTO `game_region_inventory` VALUES (8, 1, 9, 1, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-15 11:43:29', '2026-07-15 11:43:29');
INSERT INTO `game_region_inventory` VALUES (9, 1, 10, 1, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-15 11:43:43', '2026-07-15 11:43:43');
INSERT INTO `game_region_inventory` VALUES (10, 1, 11, 1, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-15 11:43:50', '2026-07-15 11:43:50');
INSERT INTO `game_region_inventory` VALUES (11, 1, 12, 1, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-15 11:43:58', '2026-07-15 11:43:58');
INSERT INTO `game_region_inventory` VALUES (12, 1, 13, 1, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-15 11:44:06', '2026-07-15 11:44:06');
INSERT INTO `game_region_inventory` VALUES (13, 1, 14, 1, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-15 11:44:15', '2026-07-15 11:44:15');
INSERT INTO `game_region_inventory` VALUES (14, 1, 15, 1, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-15 11:44:25', '2026-07-15 11:44:25');
INSERT INTO `game_region_inventory` VALUES (15, 1, 16, 1, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-15 11:44:33', '2026-07-15 11:44:33');
INSERT INTO `game_region_inventory` VALUES (16, 1, 17, 1, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-15 11:44:42', '2026-07-15 11:44:42');
INSERT INTO `game_region_inventory` VALUES (17, 1, 18, 1, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-15 11:44:50', '2026-07-15 11:44:50');
INSERT INTO `game_region_inventory` VALUES (18, 1, 19, 1, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-15 11:44:58', '2026-07-15 11:44:58');
INSERT INTO `game_region_inventory` VALUES (19, 1, 20, 1, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-15 11:45:07', '2026-07-15 11:45:07');
INSERT INTO `game_region_inventory` VALUES (20, 1, 21, 1, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-15 11:45:15', '2026-07-15 11:45:15');
INSERT INTO `game_region_inventory` VALUES (21, 1, 22, 1, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-15 11:45:24', '2026-07-15 11:45:24');
INSERT INTO `game_region_inventory` VALUES (22, 1, 23, 1, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-15 11:45:32', '2026-07-15 11:45:32');
INSERT INTO `game_region_inventory` VALUES (23, 1, 24, 1, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-15 11:45:39', '2026-07-15 11:45:39');
INSERT INTO `game_region_inventory` VALUES (24, 1, 25, 1, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-15 11:45:46', '2026-07-15 11:45:46');
INSERT INTO `game_region_inventory` VALUES (25, 1, 26, 1, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-15 11:45:53', '2026-07-15 11:45:53');
INSERT INTO `game_region_inventory` VALUES (26, 1, 27, 1, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-15 11:46:01', '2026-07-15 11:46:01');
INSERT INTO `game_region_inventory` VALUES (27, 1, 28, 1, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-15 11:46:08', '2026-07-15 11:46:08');
INSERT INTO `game_region_inventory` VALUES (28, 1, 29, 1, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-15 11:46:15', '2026-07-15 11:46:15');
INSERT INTO `game_region_inventory` VALUES (29, 1, 30, 1, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-15 11:51:12', '2026-07-15 11:51:12');
INSERT INTO `game_region_inventory` VALUES (30, 2, 37, 2, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-16 21:29:16', '2026-07-16 21:29:16');
INSERT INTO `game_region_inventory` VALUES (31, 2, 33, 2, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-16 21:29:16', '2026-07-16 21:29:16');
INSERT INTO `game_region_inventory` VALUES (32, 2, 35, 2, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-16 21:29:16', '2026-07-16 21:29:16');
INSERT INTO `game_region_inventory` VALUES (33, 2, 31, 2, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-16 21:29:16', '2026-07-16 21:29:16');
INSERT INTO `game_region_inventory` VALUES (34, 2, 32, 2, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-16 21:29:16', '2026-07-16 21:29:16');
INSERT INTO `game_region_inventory` VALUES (35, 2, 36, 2, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-16 21:29:16', '2026-07-16 21:29:16');
INSERT INTO `game_region_inventory` VALUES (36, 2, 34, 2, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-16 21:29:16', '2026-07-16 21:29:16');
INSERT INTO `game_region_inventory` VALUES (37, 2, 37, 3, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 11:17:48', '2026-07-17 11:17:48');
INSERT INTO `game_region_inventory` VALUES (38, 2, 33, 3, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 11:17:48', '2026-07-17 11:17:48');
INSERT INTO `game_region_inventory` VALUES (39, 2, 35, 3, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 11:17:48', '2026-07-17 11:17:48');
INSERT INTO `game_region_inventory` VALUES (40, 2, 31, 3, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 11:17:48', '2026-07-17 11:17:48');
INSERT INTO `game_region_inventory` VALUES (41, 2, 32, 3, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 11:17:48', '2026-07-17 11:17:48');
INSERT INTO `game_region_inventory` VALUES (42, 2, 36, 3, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 11:17:48', '2026-07-17 11:17:48');
INSERT INTO `game_region_inventory` VALUES (43, 2, 34, 3, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 11:17:48', '2026-07-17 11:17:48');
INSERT INTO `game_region_inventory` VALUES (44, 2, 37, 4, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 11:27:58', '2026-07-17 11:27:58');
INSERT INTO `game_region_inventory` VALUES (45, 2, 33, 4, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 11:27:58', '2026-07-17 11:27:58');
INSERT INTO `game_region_inventory` VALUES (46, 2, 35, 4, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 11:27:58', '2026-07-17 11:27:58');
INSERT INTO `game_region_inventory` VALUES (47, 2, 31, 4, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 11:27:58', '2026-07-17 11:27:58');
INSERT INTO `game_region_inventory` VALUES (48, 2, 32, 4, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 11:27:58', '2026-07-17 11:27:58');
INSERT INTO `game_region_inventory` VALUES (49, 2, 36, 4, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 11:27:58', '2026-07-17 11:27:58');
INSERT INTO `game_region_inventory` VALUES (50, 2, 34, 4, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 11:27:58', '2026-07-17 11:27:58');
INSERT INTO `game_region_inventory` VALUES (51, 2, 37, 5, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:14:09', '2026-07-17 12:14:09');
INSERT INTO `game_region_inventory` VALUES (52, 2, 33, 5, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:14:09', '2026-07-17 12:14:09');
INSERT INTO `game_region_inventory` VALUES (53, 2, 35, 5, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:14:09', '2026-07-17 12:14:09');
INSERT INTO `game_region_inventory` VALUES (54, 2, 31, 5, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:14:09', '2026-07-17 12:14:09');
INSERT INTO `game_region_inventory` VALUES (55, 2, 32, 5, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:14:09', '2026-07-17 12:14:09');
INSERT INTO `game_region_inventory` VALUES (56, 2, 36, 5, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:14:09', '2026-07-17 12:14:09');
INSERT INTO `game_region_inventory` VALUES (57, 2, 34, 5, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:14:09', '2026-07-17 12:14:09');
INSERT INTO `game_region_inventory` VALUES (58, 2, 37, 6, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:18:35', '2026-07-17 12:18:35');
INSERT INTO `game_region_inventory` VALUES (59, 2, 33, 6, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:18:35', '2026-07-17 12:18:35');
INSERT INTO `game_region_inventory` VALUES (60, 2, 35, 6, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:18:35', '2026-07-17 12:18:35');
INSERT INTO `game_region_inventory` VALUES (61, 2, 31, 6, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:18:35', '2026-07-17 12:18:35');
INSERT INTO `game_region_inventory` VALUES (62, 2, 32, 6, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:18:35', '2026-07-17 12:18:35');
INSERT INTO `game_region_inventory` VALUES (63, 2, 36, 6, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:18:35', '2026-07-17 12:18:35');
INSERT INTO `game_region_inventory` VALUES (64, 2, 34, 6, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:18:35', '2026-07-17 12:18:35');
INSERT INTO `game_region_inventory` VALUES (65, 2, 37, 7, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:19:34', '2026-07-17 12:19:34');
INSERT INTO `game_region_inventory` VALUES (66, 2, 33, 7, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:19:34', '2026-07-17 12:19:34');
INSERT INTO `game_region_inventory` VALUES (67, 2, 35, 7, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:19:34', '2026-07-17 12:19:34');
INSERT INTO `game_region_inventory` VALUES (68, 2, 31, 7, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:19:34', '2026-07-17 12:19:34');
INSERT INTO `game_region_inventory` VALUES (69, 2, 32, 7, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:19:34', '2026-07-17 12:19:34');
INSERT INTO `game_region_inventory` VALUES (70, 2, 36, 7, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:19:34', '2026-07-17 12:19:34');
INSERT INTO `game_region_inventory` VALUES (71, 2, 34, 7, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:19:34', '2026-07-17 12:19:34');
INSERT INTO `game_region_inventory` VALUES (72, 2, 37, 8, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:21:06', '2026-07-17 12:21:06');
INSERT INTO `game_region_inventory` VALUES (73, 2, 33, 8, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:21:06', '2026-07-17 12:21:06');
INSERT INTO `game_region_inventory` VALUES (74, 2, 35, 8, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:21:06', '2026-07-17 12:21:06');
INSERT INTO `game_region_inventory` VALUES (75, 2, 31, 8, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:21:06', '2026-07-17 12:21:06');
INSERT INTO `game_region_inventory` VALUES (76, 2, 32, 8, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:21:06', '2026-07-17 12:21:06');
INSERT INTO `game_region_inventory` VALUES (77, 2, 36, 8, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:21:06', '2026-07-17 12:21:06');
INSERT INTO `game_region_inventory` VALUES (78, 2, 34, 8, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:21:06', '2026-07-17 12:21:06');
INSERT INTO `game_region_inventory` VALUES (79, 2, 37, 9, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:21:24', '2026-07-17 12:21:24');
INSERT INTO `game_region_inventory` VALUES (80, 2, 33, 9, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:21:24', '2026-07-17 12:21:24');
INSERT INTO `game_region_inventory` VALUES (81, 2, 35, 9, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:21:24', '2026-07-17 12:21:24');
INSERT INTO `game_region_inventory` VALUES (82, 2, 31, 9, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:21:24', '2026-07-17 12:21:24');
INSERT INTO `game_region_inventory` VALUES (83, 2, 32, 9, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:21:24', '2026-07-17 12:21:24');
INSERT INTO `game_region_inventory` VALUES (84, 2, 36, 9, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:21:24', '2026-07-17 12:21:24');
INSERT INTO `game_region_inventory` VALUES (85, 2, 34, 9, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:21:24', '2026-07-17 12:21:24');
INSERT INTO `game_region_inventory` VALUES (86, 2, 37, 10, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:23:44', '2026-07-17 12:23:44');
INSERT INTO `game_region_inventory` VALUES (87, 2, 33, 10, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:23:44', '2026-07-17 12:23:44');
INSERT INTO `game_region_inventory` VALUES (88, 2, 35, 10, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:23:44', '2026-07-17 12:23:44');
INSERT INTO `game_region_inventory` VALUES (89, 2, 31, 10, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:23:44', '2026-07-17 12:23:44');
INSERT INTO `game_region_inventory` VALUES (90, 2, 32, 10, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:23:44', '2026-07-17 12:23:44');
INSERT INTO `game_region_inventory` VALUES (91, 2, 36, 10, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:23:44', '2026-07-17 12:23:44');
INSERT INTO `game_region_inventory` VALUES (92, 2, 34, 10, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:23:44', '2026-07-17 12:23:44');
INSERT INTO `game_region_inventory` VALUES (93, 2, 37, 11, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:25:54', '2026-07-17 12:25:54');
INSERT INTO `game_region_inventory` VALUES (94, 2, 33, 11, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:25:54', '2026-07-17 12:25:54');
INSERT INTO `game_region_inventory` VALUES (95, 2, 35, 11, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:25:54', '2026-07-17 12:25:54');
INSERT INTO `game_region_inventory` VALUES (96, 2, 31, 11, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:25:54', '2026-07-17 12:25:54');
INSERT INTO `game_region_inventory` VALUES (97, 2, 32, 11, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:25:54', '2026-07-17 12:25:54');
INSERT INTO `game_region_inventory` VALUES (98, 2, 36, 11, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:25:54', '2026-07-17 12:25:54');
INSERT INTO `game_region_inventory` VALUES (99, 2, 34, 11, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:25:54', '2026-07-17 12:25:54');
INSERT INTO `game_region_inventory` VALUES (100, 2, 37, 12, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:26:20', '2026-07-17 12:26:20');
INSERT INTO `game_region_inventory` VALUES (101, 2, 33, 12, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:26:20', '2026-07-17 12:26:20');
INSERT INTO `game_region_inventory` VALUES (102, 2, 35, 12, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:26:20', '2026-07-17 12:26:20');
INSERT INTO `game_region_inventory` VALUES (103, 2, 31, 12, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:26:20', '2026-07-17 12:26:20');
INSERT INTO `game_region_inventory` VALUES (104, 2, 32, 12, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:26:20', '2026-07-17 12:26:20');
INSERT INTO `game_region_inventory` VALUES (105, 2, 36, 12, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:26:20', '2026-07-17 12:26:20');
INSERT INTO `game_region_inventory` VALUES (106, 2, 34, 12, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:26:20', '2026-07-17 12:26:20');
INSERT INTO `game_region_inventory` VALUES (107, 2, 37, 13, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:38:09', '2026-07-17 12:38:09');
INSERT INTO `game_region_inventory` VALUES (108, 2, 33, 13, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:38:09', '2026-07-17 12:38:09');
INSERT INTO `game_region_inventory` VALUES (109, 2, 35, 13, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:38:09', '2026-07-17 12:38:09');
INSERT INTO `game_region_inventory` VALUES (110, 2, 31, 13, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:38:09', '2026-07-17 12:38:09');
INSERT INTO `game_region_inventory` VALUES (111, 2, 32, 13, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:38:09', '2026-07-17 12:38:09');
INSERT INTO `game_region_inventory` VALUES (112, 2, 36, 13, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:38:09', '2026-07-17 12:38:09');
INSERT INTO `game_region_inventory` VALUES (113, 2, 34, 13, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:38:09', '2026-07-17 12:38:09');
INSERT INTO `game_region_inventory` VALUES (114, 2, 37, 14, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:38:27', '2026-07-17 12:38:27');
INSERT INTO `game_region_inventory` VALUES (115, 2, 33, 14, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:38:27', '2026-07-17 12:38:27');
INSERT INTO `game_region_inventory` VALUES (116, 2, 35, 14, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:38:27', '2026-07-17 12:38:27');
INSERT INTO `game_region_inventory` VALUES (117, 2, 31, 14, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:38:27', '2026-07-17 12:38:27');
INSERT INTO `game_region_inventory` VALUES (118, 2, 32, 14, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:38:27', '2026-07-17 12:38:27');
INSERT INTO `game_region_inventory` VALUES (119, 2, 36, 14, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:38:27', '2026-07-17 12:38:27');
INSERT INTO `game_region_inventory` VALUES (120, 2, 34, 14, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:38:27', '2026-07-17 12:38:27');
INSERT INTO `game_region_inventory` VALUES (121, 2, 37, 15, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:40:34', '2026-07-17 12:40:34');
INSERT INTO `game_region_inventory` VALUES (122, 2, 33, 15, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:40:34', '2026-07-17 12:40:34');
INSERT INTO `game_region_inventory` VALUES (123, 2, 35, 15, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:40:34', '2026-07-17 12:40:34');
INSERT INTO `game_region_inventory` VALUES (124, 2, 31, 15, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:40:34', '2026-07-17 12:40:34');
INSERT INTO `game_region_inventory` VALUES (125, 2, 32, 15, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:40:34', '2026-07-17 12:40:34');
INSERT INTO `game_region_inventory` VALUES (126, 2, 36, 15, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:40:34', '2026-07-17 12:40:34');
INSERT INTO `game_region_inventory` VALUES (127, 2, 34, 15, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:40:34', '2026-07-17 12:40:34');
INSERT INTO `game_region_inventory` VALUES (128, 2, 37, 16, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:41:10', '2026-07-17 12:41:10');
INSERT INTO `game_region_inventory` VALUES (129, 2, 33, 16, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:41:10', '2026-07-17 12:41:10');
INSERT INTO `game_region_inventory` VALUES (130, 2, 35, 16, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:41:10', '2026-07-17 12:41:10');
INSERT INTO `game_region_inventory` VALUES (131, 2, 31, 16, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:41:10', '2026-07-17 12:41:10');
INSERT INTO `game_region_inventory` VALUES (132, 2, 32, 16, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:41:10', '2026-07-17 12:41:10');
INSERT INTO `game_region_inventory` VALUES (133, 2, 36, 16, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:41:10', '2026-07-17 12:41:10');
INSERT INTO `game_region_inventory` VALUES (134, 2, 34, 16, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:41:10', '2026-07-17 12:41:10');
INSERT INTO `game_region_inventory` VALUES (135, 2, 37, 17, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:41:44', '2026-07-17 12:41:44');
INSERT INTO `game_region_inventory` VALUES (136, 2, 33, 17, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:41:44', '2026-07-17 12:41:44');
INSERT INTO `game_region_inventory` VALUES (137, 2, 35, 17, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:41:44', '2026-07-17 12:41:44');
INSERT INTO `game_region_inventory` VALUES (138, 2, 31, 17, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:41:44', '2026-07-17 12:41:44');
INSERT INTO `game_region_inventory` VALUES (139, 2, 32, 17, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:41:44', '2026-07-17 12:41:44');
INSERT INTO `game_region_inventory` VALUES (140, 2, 36, 17, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:41:44', '2026-07-17 12:41:44');
INSERT INTO `game_region_inventory` VALUES (141, 2, 34, 17, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:41:44', '2026-07-17 12:41:44');
INSERT INTO `game_region_inventory` VALUES (142, 2, 37, 18, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:43:16', '2026-07-17 12:43:16');
INSERT INTO `game_region_inventory` VALUES (143, 2, 33, 18, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:43:16', '2026-07-17 12:43:16');
INSERT INTO `game_region_inventory` VALUES (144, 2, 35, 18, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:43:16', '2026-07-17 12:43:16');
INSERT INTO `game_region_inventory` VALUES (145, 2, 31, 18, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:43:16', '2026-07-17 12:43:16');
INSERT INTO `game_region_inventory` VALUES (146, 2, 32, 18, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:43:16', '2026-07-17 12:43:16');
INSERT INTO `game_region_inventory` VALUES (147, 2, 36, 18, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:43:16', '2026-07-17 12:43:16');
INSERT INTO `game_region_inventory` VALUES (148, 2, 34, 18, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:43:16', '2026-07-17 12:43:16');
INSERT INTO `game_region_inventory` VALUES (149, 2, 37, 19, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:43:38', '2026-07-17 12:43:38');
INSERT INTO `game_region_inventory` VALUES (150, 2, 33, 19, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:43:38', '2026-07-17 12:43:38');
INSERT INTO `game_region_inventory` VALUES (151, 2, 35, 19, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:43:38', '2026-07-17 12:43:38');
INSERT INTO `game_region_inventory` VALUES (152, 2, 31, 19, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:43:38', '2026-07-17 12:43:38');
INSERT INTO `game_region_inventory` VALUES (153, 2, 32, 19, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:43:38', '2026-07-17 12:43:38');
INSERT INTO `game_region_inventory` VALUES (154, 2, 36, 19, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:43:38', '2026-07-17 12:43:38');
INSERT INTO `game_region_inventory` VALUES (155, 2, 34, 19, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:43:38', '2026-07-17 12:43:38');
INSERT INTO `game_region_inventory` VALUES (156, 2, 37, 20, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:43:58', '2026-07-17 12:43:58');
INSERT INTO `game_region_inventory` VALUES (157, 2, 33, 20, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:43:58', '2026-07-17 12:43:58');
INSERT INTO `game_region_inventory` VALUES (158, 2, 35, 20, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:43:58', '2026-07-17 12:43:58');
INSERT INTO `game_region_inventory` VALUES (159, 2, 31, 20, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:43:58', '2026-07-17 12:43:58');
INSERT INTO `game_region_inventory` VALUES (160, 2, 32, 20, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:43:58', '2026-07-17 12:43:58');
INSERT INTO `game_region_inventory` VALUES (161, 2, 36, 20, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:43:58', '2026-07-17 12:43:58');
INSERT INTO `game_region_inventory` VALUES (162, 2, 34, 20, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:43:58', '2026-07-17 12:43:58');
INSERT INTO `game_region_inventory` VALUES (163, 2, 37, 21, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:44:18', '2026-07-17 12:44:18');
INSERT INTO `game_region_inventory` VALUES (164, 2, 33, 21, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:44:18', '2026-07-17 12:44:18');
INSERT INTO `game_region_inventory` VALUES (165, 2, 35, 21, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:44:18', '2026-07-17 12:44:18');
INSERT INTO `game_region_inventory` VALUES (166, 2, 31, 21, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:44:18', '2026-07-17 12:44:18');
INSERT INTO `game_region_inventory` VALUES (167, 2, 32, 21, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:44:18', '2026-07-17 12:44:18');
INSERT INTO `game_region_inventory` VALUES (168, 2, 36, 21, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:44:18', '2026-07-17 12:44:18');
INSERT INTO `game_region_inventory` VALUES (169, 2, 34, 21, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:44:18', '2026-07-17 12:44:18');
INSERT INTO `game_region_inventory` VALUES (170, 2, 37, 22, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:44:42', '2026-07-17 12:44:42');
INSERT INTO `game_region_inventory` VALUES (171, 2, 33, 22, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:44:42', '2026-07-17 12:44:42');
INSERT INTO `game_region_inventory` VALUES (172, 2, 35, 22, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:44:42', '2026-07-17 12:44:42');
INSERT INTO `game_region_inventory` VALUES (173, 2, 31, 22, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:44:42', '2026-07-17 12:44:42');
INSERT INTO `game_region_inventory` VALUES (174, 2, 32, 22, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:44:42', '2026-07-17 12:44:42');
INSERT INTO `game_region_inventory` VALUES (175, 2, 36, 22, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:44:42', '2026-07-17 12:44:42');
INSERT INTO `game_region_inventory` VALUES (176, 2, 34, 22, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:44:42', '2026-07-17 12:44:42');
INSERT INTO `game_region_inventory` VALUES (177, 2, 37, 23, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:45:00', '2026-07-17 12:45:00');
INSERT INTO `game_region_inventory` VALUES (178, 2, 33, 23, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:45:00', '2026-07-17 12:45:00');
INSERT INTO `game_region_inventory` VALUES (179, 2, 35, 23, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:45:00', '2026-07-17 12:45:00');
INSERT INTO `game_region_inventory` VALUES (180, 2, 31, 23, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:45:00', '2026-07-17 12:45:00');
INSERT INTO `game_region_inventory` VALUES (181, 2, 32, 23, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:45:00', '2026-07-17 12:45:00');
INSERT INTO `game_region_inventory` VALUES (182, 2, 36, 23, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:45:00', '2026-07-17 12:45:00');
INSERT INTO `game_region_inventory` VALUES (183, 2, 34, 23, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:45:00', '2026-07-17 12:45:00');
INSERT INTO `game_region_inventory` VALUES (184, 2, 37, 24, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:45:46', '2026-07-17 12:45:46');
INSERT INTO `game_region_inventory` VALUES (185, 2, 33, 24, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:45:46', '2026-07-17 12:45:46');
INSERT INTO `game_region_inventory` VALUES (186, 2, 35, 24, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:45:46', '2026-07-17 12:45:46');
INSERT INTO `game_region_inventory` VALUES (187, 2, 31, 24, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:45:46', '2026-07-17 12:45:46');
INSERT INTO `game_region_inventory` VALUES (188, 2, 32, 24, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:45:46', '2026-07-17 12:45:46');
INSERT INTO `game_region_inventory` VALUES (189, 2, 36, 24, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:45:46', '2026-07-17 12:45:46');
INSERT INTO `game_region_inventory` VALUES (190, 2, 34, 24, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:45:46', '2026-07-17 12:45:46');
INSERT INTO `game_region_inventory` VALUES (191, 2, 37, 25, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:45:59', '2026-07-17 12:45:59');
INSERT INTO `game_region_inventory` VALUES (192, 2, 33, 25, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:45:59', '2026-07-17 12:45:59');
INSERT INTO `game_region_inventory` VALUES (193, 2, 35, 25, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:45:59', '2026-07-17 12:45:59');
INSERT INTO `game_region_inventory` VALUES (194, 2, 31, 25, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:45:59', '2026-07-17 12:45:59');
INSERT INTO `game_region_inventory` VALUES (195, 2, 32, 25, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:45:59', '2026-07-17 12:45:59');
INSERT INTO `game_region_inventory` VALUES (196, 2, 36, 25, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:45:59', '2026-07-17 12:45:59');
INSERT INTO `game_region_inventory` VALUES (197, 2, 34, 25, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:45:59', '2026-07-17 12:45:59');
INSERT INTO `game_region_inventory` VALUES (198, 2, 37, 26, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:46:14', '2026-07-17 12:46:14');
INSERT INTO `game_region_inventory` VALUES (199, 2, 33, 26, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:46:14', '2026-07-17 12:46:14');
INSERT INTO `game_region_inventory` VALUES (200, 2, 35, 26, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:46:14', '2026-07-17 12:46:14');
INSERT INTO `game_region_inventory` VALUES (201, 2, 31, 26, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:46:14', '2026-07-17 12:46:14');
INSERT INTO `game_region_inventory` VALUES (202, 2, 32, 26, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:46:14', '2026-07-17 12:46:14');
INSERT INTO `game_region_inventory` VALUES (203, 2, 36, 26, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:46:14', '2026-07-17 12:46:14');
INSERT INTO `game_region_inventory` VALUES (204, 2, 34, 26, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:46:14', '2026-07-17 12:46:14');
INSERT INTO `game_region_inventory` VALUES (205, 2, 37, 27, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:46:27', '2026-07-17 12:46:27');
INSERT INTO `game_region_inventory` VALUES (206, 2, 33, 27, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:46:27', '2026-07-17 12:46:27');
INSERT INTO `game_region_inventory` VALUES (207, 2, 35, 27, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:46:27', '2026-07-17 12:46:27');
INSERT INTO `game_region_inventory` VALUES (208, 2, 31, 27, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:46:27', '2026-07-17 12:46:27');
INSERT INTO `game_region_inventory` VALUES (209, 2, 32, 27, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:46:27', '2026-07-17 12:46:27');
INSERT INTO `game_region_inventory` VALUES (210, 2, 36, 27, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:46:27', '2026-07-17 12:46:27');
INSERT INTO `game_region_inventory` VALUES (211, 2, 34, 27, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:46:27', '2026-07-17 12:46:27');
INSERT INTO `game_region_inventory` VALUES (212, 2, 37, 28, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:46:46', '2026-07-17 12:46:46');
INSERT INTO `game_region_inventory` VALUES (213, 2, 33, 28, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:46:46', '2026-07-17 12:46:46');
INSERT INTO `game_region_inventory` VALUES (214, 2, 35, 28, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:46:46', '2026-07-17 12:46:46');
INSERT INTO `game_region_inventory` VALUES (215, 2, 31, 28, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:46:46', '2026-07-17 12:46:46');
INSERT INTO `game_region_inventory` VALUES (216, 2, 32, 28, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:46:46', '2026-07-17 12:46:46');
INSERT INTO `game_region_inventory` VALUES (217, 2, 36, 28, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:46:46', '2026-07-17 12:46:46');
INSERT INTO `game_region_inventory` VALUES (218, 2, 34, 28, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:46:46', '2026-07-17 12:46:46');
INSERT INTO `game_region_inventory` VALUES (219, 2, 37, 29, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:47:02', '2026-07-17 12:47:02');
INSERT INTO `game_region_inventory` VALUES (220, 2, 33, 29, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:47:02', '2026-07-17 12:47:02');
INSERT INTO `game_region_inventory` VALUES (221, 2, 35, 29, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:47:02', '2026-07-17 12:47:02');
INSERT INTO `game_region_inventory` VALUES (222, 2, 31, 29, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:47:02', '2026-07-17 12:47:02');
INSERT INTO `game_region_inventory` VALUES (223, 2, 32, 29, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:47:02', '2026-07-17 12:47:02');
INSERT INTO `game_region_inventory` VALUES (224, 2, 36, 29, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:47:02', '2026-07-17 12:47:02');
INSERT INTO `game_region_inventory` VALUES (225, 2, 34, 29, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:47:02', '2026-07-17 12:47:02');
INSERT INTO `game_region_inventory` VALUES (226, 2, 37, 30, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:47:19', '2026-07-17 12:47:19');
INSERT INTO `game_region_inventory` VALUES (227, 2, 33, 30, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:47:19', '2026-07-17 12:47:19');
INSERT INTO `game_region_inventory` VALUES (228, 2, 35, 30, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:47:19', '2026-07-17 12:47:19');
INSERT INTO `game_region_inventory` VALUES (229, 2, 31, 30, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:47:19', '2026-07-17 12:47:19');
INSERT INTO `game_region_inventory` VALUES (230, 2, 32, 30, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:47:19', '2026-07-17 12:47:19');
INSERT INTO `game_region_inventory` VALUES (231, 2, 36, 30, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:47:19', '2026-07-17 12:47:19');
INSERT INTO `game_region_inventory` VALUES (232, 2, 34, 30, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:47:19', '2026-07-17 12:47:19');
INSERT INTO `game_region_inventory` VALUES (233, 2, 37, 31, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:47:35', '2026-07-17 12:47:35');
INSERT INTO `game_region_inventory` VALUES (234, 2, 33, 31, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:47:35', '2026-07-17 12:47:35');
INSERT INTO `game_region_inventory` VALUES (235, 2, 35, 31, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:47:35', '2026-07-17 12:47:35');
INSERT INTO `game_region_inventory` VALUES (236, 2, 31, 31, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:47:35', '2026-07-17 12:47:35');
INSERT INTO `game_region_inventory` VALUES (237, 2, 32, 31, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:47:35', '2026-07-17 12:47:35');
INSERT INTO `game_region_inventory` VALUES (238, 2, 36, 31, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:47:35', '2026-07-17 12:47:35');
INSERT INTO `game_region_inventory` VALUES (239, 2, 34, 31, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:47:35', '2026-07-17 12:47:35');
INSERT INTO `game_region_inventory` VALUES (240, 2, 37, 32, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:47:48', '2026-07-17 12:47:48');
INSERT INTO `game_region_inventory` VALUES (241, 2, 33, 32, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:47:48', '2026-07-17 12:47:48');
INSERT INTO `game_region_inventory` VALUES (242, 2, 35, 32, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:47:48', '2026-07-17 12:47:48');
INSERT INTO `game_region_inventory` VALUES (243, 2, 31, 32, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:47:48', '2026-07-17 12:47:48');
INSERT INTO `game_region_inventory` VALUES (244, 2, 32, 32, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:47:48', '2026-07-17 12:47:48');
INSERT INTO `game_region_inventory` VALUES (245, 2, 36, 32, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:47:48', '2026-07-17 12:47:48');
INSERT INTO `game_region_inventory` VALUES (246, 2, 34, 32, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:47:48', '2026-07-17 12:47:48');
INSERT INTO `game_region_inventory` VALUES (247, 2, 37, 33, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:48:01', '2026-07-17 12:48:01');
INSERT INTO `game_region_inventory` VALUES (248, 2, 33, 33, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:48:01', '2026-07-17 12:48:01');
INSERT INTO `game_region_inventory` VALUES (249, 2, 35, 33, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:48:01', '2026-07-17 12:48:01');
INSERT INTO `game_region_inventory` VALUES (250, 2, 31, 33, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:48:01', '2026-07-17 12:48:01');
INSERT INTO `game_region_inventory` VALUES (251, 2, 32, 33, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:48:01', '2026-07-17 12:48:01');
INSERT INTO `game_region_inventory` VALUES (252, 2, 36, 33, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:48:01', '2026-07-17 12:48:01');
INSERT INTO `game_region_inventory` VALUES (253, 2, 34, 33, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:48:01', '2026-07-17 12:48:01');
INSERT INTO `game_region_inventory` VALUES (254, 2, 37, 34, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:48:20', '2026-07-17 12:48:20');
INSERT INTO `game_region_inventory` VALUES (255, 2, 33, 34, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:48:20', '2026-07-17 12:48:20');
INSERT INTO `game_region_inventory` VALUES (256, 2, 35, 34, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:48:20', '2026-07-17 12:48:20');
INSERT INTO `game_region_inventory` VALUES (257, 2, 31, 34, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:48:20', '2026-07-17 12:48:20');
INSERT INTO `game_region_inventory` VALUES (258, 2, 32, 34, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:48:20', '2026-07-17 12:48:20');
INSERT INTO `game_region_inventory` VALUES (259, 2, 36, 34, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:48:20', '2026-07-17 12:48:20');
INSERT INTO `game_region_inventory` VALUES (260, 2, 34, 34, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:48:20', '2026-07-17 12:48:20');
INSERT INTO `game_region_inventory` VALUES (261, 2, 37, 35, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:48:37', '2026-07-17 12:48:37');
INSERT INTO `game_region_inventory` VALUES (262, 2, 33, 35, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:48:37', '2026-07-17 12:48:37');
INSERT INTO `game_region_inventory` VALUES (263, 2, 35, 35, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:48:37', '2026-07-17 12:48:37');
INSERT INTO `game_region_inventory` VALUES (264, 2, 31, 35, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:48:37', '2026-07-17 12:48:37');
INSERT INTO `game_region_inventory` VALUES (265, 2, 32, 35, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:48:37', '2026-07-17 12:48:37');
INSERT INTO `game_region_inventory` VALUES (266, 2, 36, 35, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:48:37', '2026-07-17 12:48:37');
INSERT INTO `game_region_inventory` VALUES (267, 2, 34, 35, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:48:37', '2026-07-17 12:48:37');
INSERT INTO `game_region_inventory` VALUES (268, 2, 37, 36, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:48:56', '2026-07-17 12:48:56');
INSERT INTO `game_region_inventory` VALUES (269, 2, 33, 36, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:48:56', '2026-07-17 12:48:56');
INSERT INTO `game_region_inventory` VALUES (270, 2, 35, 36, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:48:56', '2026-07-17 12:48:56');
INSERT INTO `game_region_inventory` VALUES (271, 2, 31, 36, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:48:56', '2026-07-17 12:48:56');
INSERT INTO `game_region_inventory` VALUES (272, 2, 32, 36, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:48:56', '2026-07-17 12:48:56');
INSERT INTO `game_region_inventory` VALUES (273, 2, 36, 36, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:48:56', '2026-07-17 12:48:56');
INSERT INTO `game_region_inventory` VALUES (274, 2, 34, 36, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:48:56', '2026-07-17 12:48:56');
INSERT INTO `game_region_inventory` VALUES (275, 2, 37, 37, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:51:32', '2026-07-17 12:51:32');
INSERT INTO `game_region_inventory` VALUES (276, 2, 33, 37, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:51:32', '2026-07-17 12:51:32');
INSERT INTO `game_region_inventory` VALUES (277, 2, 35, 37, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:51:32', '2026-07-17 12:51:32');
INSERT INTO `game_region_inventory` VALUES (278, 2, 31, 37, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:51:32', '2026-07-17 12:51:32');
INSERT INTO `game_region_inventory` VALUES (279, 2, 32, 37, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:51:32', '2026-07-17 12:51:32');
INSERT INTO `game_region_inventory` VALUES (280, 2, 36, 37, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:51:32', '2026-07-17 12:51:32');
INSERT INTO `game_region_inventory` VALUES (281, 2, 34, 37, 0, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 1, '2026-07-17 12:51:32', '2026-07-17 12:51:32');

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
) ENGINE = InnoDB AUTO_INCREMENT = 38 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '游戏大区表' ROW_FORMAT = DYNAMIC;

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
INSERT INTO `game_regions` VALUES (31, 2, '서버전체', '서버전체', 1, 1, '2026-07-16 14:37:14', '2026-07-16 14:37:14');
INSERT INTO `game_regions` VALUES (32, 2, '스탠다드', '스탠다드', 2, 1, '2026-07-16 14:37:23', '2026-07-16 14:37:23');
INSERT INTO `game_regions` VALUES (33, 2, '래더', '래더', 3, 1, '2026-07-16 14:37:33', '2026-07-16 14:37:33');
INSERT INTO `game_regions` VALUES (34, 2, '하드코어', '하드코어', 4, 1, '2026-07-16 14:37:42', '2026-07-16 14:37:42');
INSERT INTO `game_regions` VALUES (35, 2, '래더하드코어', '래더하드코어', 5, 1, '2026-07-16 14:37:52', '2026-07-16 14:37:52');
INSERT INTO `game_regions` VALUES (36, 2, '테스트', '테스트', 6, 1, '2026-07-16 14:38:04', '2026-07-16 14:38:04');
INSERT INTO `game_regions` VALUES (37, 2, '기타', '기타', 7, 1, '2026-07-16 14:38:12', '2026-07-16 14:38:12');

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
  `image_url` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '招呼图片URL',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_game`(`game_id` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 5 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '游戏话术表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of game_scripts
-- ----------------------------
INSERT INTO `game_scripts` VALUES (1, 1, '你好', '안녕하세요', '招呼', 0, 1, '2026-07-16 14:50:36', '2026-07-16 14:50:36', '');
INSERT INTO `game_scripts` VALUES (2, 1, '请到说话岛仓库下面找我', '말하는섬 창고  밑에서 저를 찾으십시오', '招呼', 1, 1, '2026-07-16 15:24:46', '2026-07-16 15:24:46', '');
INSERT INTO `game_scripts` VALUES (3, 2, '你好', '안녕하세요', '招呼', 0, 1, '2026-07-16 20:17:25', '2026-07-16 20:17:25', '');
INSERT INTO `game_scripts` VALUES (4, 2, '房间号', '1803/1205', '招呼', 1, 1, '2026-07-16 20:17:47', '2026-07-16 20:17:47', '');

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
  `trade_type` enum('web','script') CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL DEFAULT 'script' COMMENT '交易执行分类: web/script',
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
INSERT INTO `games` VALUES (1, '天堂经典版', '리니지클래식', '', 'PC', '', 'script', 0, 1, '2026-07-15 11:01:45', '2026-07-15 11:01:45');
INSERT INTO `games` VALUES (2, '暗黑2:休闲版', '디아블로2:레저렉션', '', 'PC', '', 'script', 1, 1, '2026-07-15 11:02:42', '2026-07-15 11:02:42');

-- ----------------------------
-- Table structure for machine_accounts
-- ----------------------------
DROP TABLE IF EXISTS `machine_platform_accounts`;
CREATE TABLE `machine_platform_accounts`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `machine_id` int NOT NULL COMMENT '机器ID',
  `account_id` int NOT NULL COMMENT '网站账户ID',
  `is_active` tinyint NOT NULL DEFAULT 1,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uk_machine_account`(`machine_id` ASC, `account_id` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 3 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '机器关联网站账户' ROW_FORMAT = Dynamic;

-- ----------------------------
-- Records of machine_accounts
-- ----------------------------

-- ----------------------------
-- Table structure for machine_games
-- ----------------------------
DROP TABLE IF EXISTS `machine_game_accounts`;
CREATE TABLE `machine_game_accounts`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `machine_id` int NOT NULL COMMENT '关联机器ID',
  `game_account_id` int NOT NULL COMMENT '关联游戏账号ID',
  `region_id` int NOT NULL COMMENT '关联大区ID',
  `priority` int NULL DEFAULT 0 COMMENT '优先级(数字越大优先级越高)',
  `max_concurrent` int NULL DEFAULT 1 COMMENT '最大并发订单数',
  `is_active` tinyint(1) NULL DEFAULT 1,
  `created_at` datetime NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uk_machine_game_account_region`(`machine_id` ASC, `game_account_id` ASC, `region_id` ASC) USING BTREE,
  INDEX `region_id`(`region_id` ASC) USING BTREE,
  INDEX `game_account_id`(`game_account_id` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 1 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '机器关联游戏表' ROW_FORMAT = DYNAMIC;

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
  `mk_device_id` int NULL DEFAULT NULL COMMENT '关联鼠标键盘设备ID(一对一)',
  `vs_device_id` int NULL DEFAULT NULL COMMENT '关联视频流设备ID(一对一)',
  `last_heartbeat` datetime NULL DEFAULT NULL COMMENT '最后心跳时间',
  `remark` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL COMMENT '备注',
  `is_active` tinyint(1) NULL DEFAULT 1,
  `created_at` datetime NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uk_mac`(`mac_address` ASC) USING BTREE,
  UNIQUE INDEX `uk_mk_device`(`mk_device_id` ASC) USING BTREE,
  UNIQUE INDEX `uk_vs_device`(`vs_device_id` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 2 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '机器表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of machines
-- ----------------------------
INSERT INTO `machines` VALUES (1, 'A8:2B:DD:1B:73:5A', '白金之星', '10.64.0.2', '测试机', 'Windows 11', 'online', NULL, NULL, '2026-07-19 14:47:17', NULL, 1, '2026-07-15 10:51:49', '2026-07-15 10:51:49');

-- ----------------------------
-- Table structure for mouse_keyboard_devices
-- ----------------------------
DROP TABLE IF EXISTS `mouse_keyboard_devices`;
CREATE TABLE `mouse_keyboard_devices`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '设备名称',
  `device_type` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '设备类型(如USB/蓝牙)',
  `device_info` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '设备信息(如设备ID/序列号)',
  `remark` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL COMMENT '备注',
  `is_active` tinyint(1) NULL DEFAULT 1,
  `created_at` datetime NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '鼠标键盘设备表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of mouse_keyboard_devices
-- ----------------------------

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
  `image_url` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '招呼图片URL',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `game_script_id`(`game_script_id` ASC) USING BTREE,
  INDEX `idx_region`(`region_id` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 2 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '大区话术表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of region_scripts
-- ----------------------------
INSERT INTO `region_scripts` VALUES (1, 4, NULL, '位置图片', '', '', '招呼', 0, 1, '2026-07-16 15:29:25', '2026-07-16 15:29:25', '/uploads/images/c21f1a0d1453402082bfbf43a4ffed96.png');

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
) ENGINE = InnoDB AUTO_INCREMENT = 1 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '自动交易指派' ROW_FORMAT = DYNAMIC;

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
) ENGINE = InnoDB AUTO_INCREMENT = 43 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '自动交易事件日志' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of trade_events
-- ----------------------------
INSERT INTO `trade_events` VALUES (3, 6, NULL, 'order_detected', 'detected', 'suspended', 'machine=1, platform=itemmania', NULL, '2026-07-16 14:20:20');
INSERT INTO `trade_events` VALUES (4, 7, NULL, 'order_detected', 'detected', 'waiting_assignment', 'machine=1, platform=itemmania', NULL, '2026-07-16 14:20:20');
INSERT INTO `trade_events` VALUES (5, 8, NULL, 'order_detected', 'detected', 'greeting', 'machine=1, platform=itemmania', NULL, '2026-07-16 15:33:42');
INSERT INTO `trade_events` VALUES (6, 9, NULL, 'order_detected', 'detected', 'greeting', 'machine=1, platform=itemmania', NULL, '2026-07-16 15:33:42');
INSERT INTO `trade_events` VALUES (7, 10, NULL, 'order_detected', 'detected', 'greeting', 'machine=1, platform=itemmania', NULL, '2026-07-16 16:17:29');
INSERT INTO `trade_events` VALUES (8, 9, NULL, 'greeting_result', 'greeting', 'suspended', '招呼执行异常: Page.wait_for_timeout: Target page, context or browser has been closed', NULL, '2026-07-16 16:36:22');
INSERT INTO `trade_events` VALUES (9, 11, NULL, 'order_detected', 'detected', 'greeting', 'machine=1, platform=itemmania', NULL, '2026-07-16 16:45:30');
INSERT INTO `trade_events` VALUES (10, 11, NULL, 'greeting_failed', 'greeting', 'greeting', '招呼发送超时（120s）', NULL, '2026-07-16 16:47:30');
INSERT INTO `trade_events` VALUES (11, 11, NULL, 'greeting_failed', 'greeting', 'greeting', '招呼执行异常: Page.goto: Target page, context or browser has been closed', NULL, '2026-07-16 16:54:06');
INSERT INTO `trade_events` VALUES (12, 11, NULL, 'greeting_failed', 'greeting', 'greeting', '招呼发送超时（120s）', NULL, '2026-07-16 17:09:37');
INSERT INTO `trade_events` VALUES (13, 11, NULL, 'greeting_failed', 'greeting', 'greeting', '招呼发送超时（120s）', NULL, '2026-07-16 17:16:06');
INSERT INTO `trade_events` VALUES (14, 11, NULL, 'greeting_failed', 'greeting', 'greeting', '招呼发送超时（120s）', NULL, '2026-07-16 17:25:06');
INSERT INTO `trade_events` VALUES (15, 11, NULL, 'greeting_failed', 'greeting', 'greeting', '招呼执行异常: Page.evaluate() takes from 2 to 3 positional arguments but 4 were given', NULL, '2026-07-16 17:35:57');
INSERT INTO `trade_events` VALUES (16, 11, NULL, 'greeting_failed', 'greeting', 'greeting', '招呼执行异常: Page.evaluate() takes from 2 to 3 positional arguments but 4 were given', NULL, '2026-07-16 17:45:55');
INSERT INTO `trade_events` VALUES (17, 11, NULL, 'greeting_failed', 'greeting', 'greeting', '招呼执行异常: Page.evaluate() takes from 2 to 3 positional arguments but 4 were given', NULL, '2026-07-16 18:07:00');
INSERT INTO `trade_events` VALUES (18, 11, NULL, 'greeting_failed', 'greeting', 'greeting', '招呼执行异常: Page.evaluate() takes from 2 to 3 positional arguments but 4 were given', NULL, '2026-07-16 18:11:50');
INSERT INTO `trade_events` VALUES (19, 11, NULL, 'greeting_failed', 'greeting', 'greeting', 'event loop 未初始化', NULL, '2026-07-16 19:15:02');
INSERT INTO `trade_events` VALUES (20, 11, NULL, 'greeting_failed', 'greeting', 'greeting', '招呼执行异常: \'BrowserSession\' object has no attribute \'acquire_chat_sender\'', NULL, '2026-07-16 19:17:48');
INSERT INTO `trade_events` VALUES (21, 11, NULL, 'greeting_failed', 'greeting', 'greeting', '招呼执行异常: Page.evaluate() takes from 2 to 3 positional arguments but 4 were given', NULL, '2026-07-16 20:04:22');
INSERT INTO `trade_events` VALUES (22, 11, NULL, 'greeting_result', 'greeting', 'waiting_assignment', '招呼发送成功', NULL, '2026-07-16 20:10:38');
INSERT INTO `trade_events` VALUES (23, 8, NULL, 'greeting_result', 'greeting', 'waiting_assignment', NULL, NULL, '2026-07-16 20:10:56');
INSERT INTO `trade_events` VALUES (24, 12, NULL, 'order_detected', 'detected', 'greeting', 'machine=1, platform=itemmania', NULL, '2026-07-16 20:14:48');
INSERT INTO `trade_events` VALUES (25, 13, NULL, 'order_detected', 'detected', 'greeting', 'machine=1, platform=itemmania', NULL, '2026-07-16 20:14:48');
INSERT INTO `trade_events` VALUES (26, 14, NULL, 'order_detected', 'detected', 'greeting', 'machine=1, platform=itemmania', NULL, '2026-07-16 20:40:59');
INSERT INTO `trade_events` VALUES (27, 15, NULL, 'order_detected', 'detected', 'greeting', 'machine=1, platform=itemmania', NULL, '2026-07-16 20:40:59');
INSERT INTO `trade_events` VALUES (28, 14, NULL, 'greeting_result', 'greeting', 'waiting_assignment', '招呼发送成功', NULL, '2026-07-16 20:41:05');
INSERT INTO `trade_events` VALUES (29, 15, NULL, 'greeting_failed', 'greeting', 'greeting', '招呼部分失败: 第3条图片发送失败: Locator.click: Timeout 30000ms exceeded.\nCall log:\n  - waiting for locator(\"#attach_layer .btn_send\")\n    - locator resolved to <button type=\"button\" class=\"btn_send\">전송</button>\n  - attempting click action\n    2 × waiting for element to be visible, enabled and stable\n      - element is not visible\n    - retrying click action\n    - waiting 20ms\n    2 × waiting for element to be visible, enabled and stable\n      - element is not visible\n    - retrying click action\n      - waiting 100ms\n    57 × waiting for element to be visible, enabled and stable\n       - element is not visible\n     - retrying click action\n       - waiting 500ms\n', NULL, '2026-07-16 20:41:36');
INSERT INTO `trade_events` VALUES (30, 15, NULL, 'greeting_result', 'greeting', 'waiting_assignment', '招呼发送成功', NULL, '2026-07-16 20:49:04');
INSERT INTO `trade_events` VALUES (31, 16, NULL, 'order_detected', 'detected', 'greeting', 'machine=1, platform=itemmania', NULL, '2026-07-16 20:51:35');
INSERT INTO `trade_events` VALUES (32, 16, NULL, 'greeting_failed', 'greeting', 'greeting', '招呼部分失败: 第3条图片发送失败: Locator.click: Element is not visible\nCall log:\n  - waiting for locator(\"#attach_layer .btn_send\")\n    - locator resolved to <button type=\"button\" class=\"btn_send\">전송</button>\n  - attempting click action\n    - scrolling into view if needed\n', NULL, '2026-07-16 20:51:42');
INSERT INTO `trade_events` VALUES (33, 17, NULL, 'order_detected', 'detected', 'greeting', 'machine=1, platform=itemmania', NULL, '2026-07-16 21:04:47');
INSERT INTO `trade_events` VALUES (34, 17, NULL, 'greeting_result', 'greeting', 'waiting_assignment', '招呼发送成功', NULL, '2026-07-16 21:05:05');
INSERT INTO `trade_events` VALUES (35, 18, NULL, 'order_detected', 'detected', 'greeting', 'machine=1, platform=itemmania', NULL, '2026-07-16 21:11:02');
INSERT INTO `trade_events` VALUES (36, 18, NULL, 'greeting_result', 'greeting', 'waiting_assignment', '招呼发送成功', NULL, '2026-07-16 21:11:21');
INSERT INTO `trade_events` VALUES (37, 19, NULL, 'order_detected', 'detected', 'greeting', 'machine=1, platform=itemmania', NULL, '2026-07-16 21:18:49');
INSERT INTO `trade_events` VALUES (38, 19, NULL, 'greeting_result', 'greeting', 'waiting_assignment', '招呼发送成功', NULL, '2026-07-16 21:19:08');
INSERT INTO `trade_events` VALUES (39, 20, NULL, 'order_detected', 'detected', 'greeting', 'machine=1, platform=itemmania', NULL, '2026-07-16 21:31:31');
INSERT INTO `trade_events` VALUES (40, 21, NULL, 'order_detected', 'detected', 'greeting', 'machine=1, platform=itemmania', NULL, '2026-07-16 21:31:31');
INSERT INTO `trade_events` VALUES (41, 20, NULL, 'greeting_result', 'greeting', 'waiting_assignment', '招呼发送成功', NULL, '2026-07-16 21:31:38');
INSERT INTO `trade_events` VALUES (42, 21, NULL, 'greeting_result', 'greeting', 'waiting_assignment', '招呼发送成功', NULL, '2026-07-16 21:31:49');

-- ----------------------------
-- Table structure for video_stream_devices
-- ----------------------------
DROP TABLE IF EXISTS `video_stream_devices`;
CREATE TABLE `video_stream_devices`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '设备名称',
  `device_type` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '设备类型(如摄像头/采集卡)',
  `device_info` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '设备信息',
  `remark` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL COMMENT '备注',
  `is_active` tinyint(1) NULL DEFAULT 1,
  `created_at` datetime NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '视频流设备表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of video_stream_devices
-- ----------------------------

-- ----------------------------
-- Table structure for website_schedules
-- ----------------------------
DROP TABLE IF EXISTS `platform_schedules`;
CREATE TABLE `platform_schedules`  (
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
INSERT INTO `platform_schedules` VALUES (1, 1, '刷新上架货品', 'refresh_up_goods', -1, 'scheduled', NULL, '40', 'uploads/audio/81035b19e00b414ca41b31a0d925533b.mp3', 1, '2026-07-07 16:36:04', '2026-07-07 17:07:39');

-- ----------------------------
-- Table structure for websites
-- ----------------------------
DROP TABLE IF EXISTS `platforms`;
CREATE TABLE `platforms`  (
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
INSERT INTO `platforms` VALUES (1, 'mania', 'https://www.itemmania.com/portal/user/p_login_form.html', '', '', 'form', '{\"success_url\": \"\", \"submit_selector\": \"#login_before button[type=submit]\", \"captcha_selector\": \"\", \"password_selector\": \"#user_password\", \"username_selector\": \"#user_id\", \"captcha_input_selector\": \"\"}', '', 1, 1, '2026-07-07 15:57:22', '2026-07-08 12:18:07');
INSERT INTO `platforms` VALUES (2, 'arotem', 'https://www.barotem.com/auth/login', '', '', 'captcha', '{\"success_url\": \"\", \"submit_selector\": \".login_btn\", \"captcha_selector\": \"\", \"password_selector\": \"#memberPass\", \"username_selector\": \"#memberId\", \"captcha_input_selector\": \"\"}', '', 2, 1, '2026-07-07 16:00:55', '2026-07-15 10:58:16');
INSERT INTO `platforms` VALUES (3, 'itemBay', 'https://www.itembay.com/login/loginAdult', '', '', 'form', '{\"success_url\": \"\", \"submit_selector\": \"div.btn_login\", \"captcha_selector\": \"\", \"password_selector\": \"#txtPassword\", \"username_selector\": \"#txtMemberID\", \"captcha_input_selector\": \"\"}', '', 3, 1, '2026-07-07 16:03:08', '2026-07-15 10:58:16');

SET FOREIGN_KEY_CHECKS = 1;
