CREATE TABLE IF NOT EXISTS `game_region_items` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `game_id` int(11) NOT NULL COMMENT '游戏ID',
  `region_id` int(11) NOT NULL COMMENT '大区ID',
  `item_id` int(11) NOT NULL COMMENT '物品ID',
  `stock` int(11) NOT NULL DEFAULT '0' COMMENT '库存数量',
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_region_item` (`region_id`, `item_id`),
  KEY `idx_game_id` (`game_id`),
  KEY `idx_region_id` (`region_id`),
  KEY `idx_item_id` (`item_id`),
  CONSTRAINT `fk_gri_game_id` FOREIGN KEY (`game_id`) REFERENCES `games` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_gri_region_id` FOREIGN KEY (`region_id`) REFERENCES `game_regions` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_gri_item_id` FOREIGN KEY (`item_id`) REFERENCES `game_items` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='大区物品库存表';
