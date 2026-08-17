-- 修复历史乱码注释，并将系统告警从“按来源覆盖一行”升级为可追踪的生命周期记录。

ALTER TABLE item_bundle_relations
    MODIFY COLUMN id INT NOT NULL AUTO_INCREMENT COMMENT '关系记录ID',
    MODIFY COLUMN bundle_id INT NOT NULL COMMENT '套装物品ID',
    MODIFY COLUMN item_id INT NOT NULL COMMENT '套装成员物品ID',
    MODIFY COLUMN quantity INT NOT NULL DEFAULT 1 COMMENT '成员物品数量',
    MODIFY COLUMN sort_order INT DEFAULT 0 COMMENT '成员显示顺序',
    MODIFY COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    COMMENT='物品套装组成关系：定义套装物品包含的成员物品及数量';

ALTER TABLE game_item_order_details
    MODIFY COLUMN item_selected_image VARCHAR(500) DEFAULT NULL
        COMMENT '物品选中状态图片URL（用于图像识别）';

ALTER TABLE game_item_orders
    MODIFY COLUMN platform_price DECIMAL(12,2) DEFAULT NULL COMMENT '平台订单成交价格',
    MODIFY COLUMN platform_item_type VARCHAR(32) DEFAULT NULL
        COMMENT '平台物品分类（游戏币、物品、账号等）',
    MODIFY COLUMN trade_item_name VARCHAR(200) DEFAULT NULL
        COMMENT '实际交易物品名（从商品标题的百分号标记中解析，用于匹配子订单）';

ALTER TABLE game_items
    MODIFY COLUMN selected_image VARCHAR(500) DEFAULT NULL
        COMMENT '物品选中状态图片URL（用于确认游戏内选择）',
    MODIFY COLUMN position VARCHAR(50) DEFAULT NULL
        COMMENT '物品在游戏界面中的参考坐标，格式为X:100,Y:200';

ALTER TABLE game_regions
    MODIFY COLUMN select_x INT DEFAULT NULL
        COMMENT '1280×960游戏客户区服务器列表中的X坐标',
    MODIFY COLUMN select_y INT DEFAULT NULL
        COMMENT '1280×960游戏客户区服务器列表中的Y坐标',
    MODIFY COLUMN select_page INT NOT NULL DEFAULT 1
        COMMENT '服务器列表页码，从1开始';

ALTER TABLE system_alerts
    DROP INDEX uk_system_alert_source_key,
    MODIFY COLUMN id BIGINT NOT NULL AUTO_INCREMENT COMMENT '告警记录ID',
    MODIFY COLUMN alert_type VARCHAR(64) NOT NULL COMMENT '告警类型编码',
    MODIFY COLUMN source_key VARCHAR(160) NOT NULL COMMENT '告警来源稳定标识',
    MODIFY COLUMN machine_id INT DEFAULT NULL COMMENT '关联机器ID',
    MODIFY COLUMN account_id INT DEFAULT NULL COMMENT '关联平台账号ID',
    MODIFY COLUMN severity VARCHAR(24) NOT NULL DEFAULT 'danger' COMMENT '严重级别',
    MODIFY COLUMN title VARCHAR(160) NOT NULL COMMENT '告警标题',
    MODIFY COLUMN message VARCHAR(1000) NOT NULL COMMENT '告警原因和处理建议',
    MODIFY COLUMN status VARCHAR(24) NOT NULL DEFAULT 'open' COMMENT '生命周期状态：open/dismissed',
    MODIFY COLUMN occurred_at DATETIME NOT NULL COMMENT '本次告警首次发生时间',
    MODIFY COLUMN dismissed_at DATETIME DEFAULT NULL COMMENT '本次告警关闭时间',
    MODIFY COLUMN created_at DATETIME NOT NULL COMMENT '记录创建时间',
    MODIFY COLUMN updated_at DATETIME NOT NULL COMMENT '记录最后更新时间',
    ADD COLUMN occurrence_count INT NOT NULL DEFAULT 1
        COMMENT '本次告警未关闭期间累计发生次数' AFTER status,
    ADD COLUMN last_occurred_at DATETIME DEFAULT NULL
        COMMENT '本次告警最近发生时间' AFTER occurred_at,
    ADD COLUMN presentation_count INT NOT NULL DEFAULT 0
        COMMENT '告警送达中控界面的次数' AFTER dismissed_at,
    ADD COLUMN last_presented_at DATETIME DEFAULT NULL
        COMMENT '最近送达中控界面的时间' AFTER presentation_count,
    ADD COLUMN voice_notification_count INT NOT NULL DEFAULT 0
        COMMENT '中控语音播报启动次数' AFTER last_presented_at,
    ADD COLUMN last_voice_notified_at DATETIME DEFAULT NULL
        COMMENT '最近一次语音播报启动时间' AFTER voice_notification_count,
    ADD COLUMN close_type VARCHAR(32) DEFAULT NULL
        COMMENT '关闭方式：manual_dismissed/auto_recovered/legacy_unknown' AFTER last_voice_notified_at,
    ADD COLUMN close_reason VARCHAR(500) DEFAULT NULL
        COMMENT '关闭原因' AFTER close_type,
    ADD COLUMN closed_by VARCHAR(100) DEFAULT NULL
        COMMENT '关闭操作方' AFTER close_reason,
    ADD COLUMN active_source_key VARCHAR(160)
        GENERATED ALWAYS AS (CASE WHEN status = 'open' THEN source_key ELSE NULL END) STORED
        COMMENT '仅开放告警使用的并发去重键' AFTER source_key,
    ADD UNIQUE KEY uk_system_alert_open_source (active_source_key),
    ADD KEY idx_system_alert_source_history (source_key, id),
    COMMENT='系统告警生命周期主表：关闭后相同来源再次告警会新增记录';

-- 旧结构的 occurred_at 实际保存最后一次刷新时间，created_at 保存首次建行时间。
-- 无法恢复旧版本已经覆盖掉的每一次事件，只能标记为历史聚合数据并保留首末时间。
UPDATE system_alerts
SET last_occurred_at = occurred_at,
    occurrence_count = CASE WHEN created_at < occurred_at THEN 2 ELSE 1 END,
    close_type = CASE WHEN status = 'dismissed' THEN 'legacy_unknown' ELSE NULL END,
    close_reason = CASE WHEN status = 'dismissed'
        THEN '历史数据由旧版覆盖式记录迁移，准确发生次数和关闭来源无法恢复' ELSE NULL END,
    closed_by = CASE WHEN status = 'dismissed' THEN 'legacy' ELSE NULL END,
    occurred_at = LEAST(created_at, occurred_at);

ALTER TABLE system_alerts
    MODIFY COLUMN last_occurred_at DATETIME NOT NULL COMMENT '本次告警最近发生时间';

CREATE TABLE IF NOT EXISTS system_alert_events (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT '告警事件ID',
    alert_id BIGINT NOT NULL COMMENT '关联system_alerts告警记录ID',
    event_type VARCHAR(32) NOT NULL
        COMMENT '事件类型：opened/refreshed/presented/voice_started/voice_completed/voice_failed/manual_dismissed/auto_recovered/legacy_imported',
    event_at DATETIME NOT NULL COMMENT '事件发生时间',
    actor VARCHAR(100) NOT NULL COMMENT '事件产生方',
    details VARCHAR(1000) DEFAULT NULL COMMENT '事件说明或失败原因',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '事件入库时间',
    PRIMARY KEY (id),
    KEY idx_system_alert_event_alert_time (alert_id, event_at, id),
    KEY idx_system_alert_event_type_time (event_type, event_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='系统告警只追加事件流水，用于追踪产生、展示、播报和关闭全过程';

INSERT INTO system_alert_events (
    alert_id, event_type, event_at, actor, details, created_at
)
SELECT id,
       'legacy_imported',
       created_at,
       'migration',
       '从旧版覆盖式system_alerts记录迁入；迁移前的完整刷新和通知流水无法恢复',
       NOW()
FROM system_alerts alert
WHERE NOT EXISTS (
    SELECT 1
    FROM system_alert_events event
    WHERE event.alert_id = alert.id
      AND event.event_type = 'legacy_imported'
);
