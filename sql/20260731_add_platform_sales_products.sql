CREATE TABLE IF NOT EXISTS platform_sales_products (
    id INT NOT NULL AUTO_INCREMENT,
    website_id INT NOT NULL,
    platform_account_id INT NOT NULL,
    platform VARCHAR(32) NOT NULL,
    platform_product_id VARCHAR(100) NOT NULL,
    platform_item_type VARCHAR(32) NOT NULL DEFAULT '',
    game_id INT NULL,
    region_id INT NULL,
    game_item_id INT NULL,
    game_name VARCHAR(100) NOT NULL DEFAULT '',
    region_name VARCHAR(100) NOT NULL DEFAULT '',
    title VARCHAR(500) NOT NULL DEFAULT '',
    parsed_item_name VARCHAR(255) NOT NULL DEFAULT '',
    parse_status VARCHAR(32) NOT NULL,
    parse_error VARCHAR(500) NOT NULL DEFAULT '',
    quantity_text VARCHAR(100) NOT NULL DEFAULT '',
    price_text VARCHAR(100) NOT NULL DEFAULT '',
    platform_registered_at VARCHAR(64) NOT NULL DEFAULT '',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_platform_sales_product_account_product (
        platform_account_id,
        platform_product_id
    ),
    KEY idx_platform_sales_products_website (website_id),
    KEY idx_platform_sales_products_game_region (game_id, region_id),
    KEY idx_platform_sales_products_game_item (game_item_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='平台账号当前实际在售商品镜像';
