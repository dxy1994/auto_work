-- 初始安装数据（网站、账号、调度配置）
-- 合并自: websites_1.sql, accounts_1.sql, website_schedules_1.sql

SET NAMES utf8mb4;
USE `auto_login`;

-- ============================================================
-- 网站初始数据
-- ============================================================
INSERT INTO auto_login.websites (id, name, url, icon, category, login_type, login_config, remark, sort_order, is_active, created_at, updated_at) VALUES (1, 'mania', 'https://www.itemmania.com/portal/user/p_login_form.html', '', '', 'form', '{"success_url": "", "submit_selector": "#login_before button[type=submit]", "captcha_selector": "", "password_selector": "#user_password", "username_selector": "#user_id", "captcha_input_selector": ""}', '', 0, 1, '2026-07-07 15:57:22', '2026-07-08 12:18:07');
INSERT INTO auto_login.websites (id, name, url, icon, category, login_type, login_config, remark, sort_order, is_active, created_at, updated_at) VALUES (2, 'arotem', 'https://www.barotem.com/auth/login', '', '', 'captcha', '{"success_url": "", "submit_selector": ".login_btn", "captcha_selector": "", "password_selector": "#memberPass", "username_selector": "#memberId", "captcha_input_selector": ""}', '', 1, 1, '2026-07-07 16:00:55', '2026-07-07 16:00:55');
INSERT INTO auto_login.websites (id, name, url, icon, category, login_type, login_config, remark, sort_order, is_active, created_at, updated_at) VALUES (3, 'itemBay', 'https://www.itembay.com/login/loginAdult', '', '', 'form', '{"success_url": "", "submit_selector": "div.btn_login", "captcha_selector": "", "password_selector": "#txtPassword", "username_selector": "#txtMemberID", "captcha_input_selector": ""}', '', 2, 1, '2026-07-07 16:03:08', '2026-07-07 16:03:08');

-- ============================================================
-- 账号初始数据
-- ============================================================
INSERT INTO auto_login.accounts (id, website_id, label, username, password, extra_fields, is_default, is_active, created_at, updated_at) VALUES (1, 3, '1', 'awj810105', 'CYasgwT1Dg7H/lo1zl8uLPZz68KtYCt8rLoAHgP6HM8=', 'null', 1, 1, '2026-07-07 16:03:54', '2026-07-07 16:03:54');
INSERT INTO auto_login.accounts (id, website_id, label, username, password, extra_fields, is_default, is_active, created_at, updated_at) VALUES (2, 1, '1', 'yongchun1225', 'LjdPkFTrgiMthwbhFMEyn37lAcEIwnPboU9TIww/jPs=', 'null', 1, 1, '2026-07-07 16:04:22', '2026-07-07 16:05:11');
INSERT INTO auto_login.accounts (id, website_id, label, username, password, extra_fields, is_default, is_active, created_at, updated_at) VALUES (3, 2, '1', 'yongchun1224', 'Yzdj8uX0fYDtHwCWa/DBBguyHGvQ31fOKCtV2V3AWOk=', 'null', 1, 1, '2026-07-07 16:04:49', '2026-07-07 16:04:49');
INSERT INTO auto_login.accounts (id, website_id, label, username, password, extra_fields, is_default, is_active, created_at, updated_at) VALUES (4, 1, '2', 'khs20020403', '+1piJEauhdvC+omzuk6AE7uyfw6k8DJq4yIgZVq9kyI=', 'null', 0, 1, '2026-07-08 11:39:34', '2026-07-08 11:39:34');

-- ============================================================
-- 网站调度配置初始数据
-- ============================================================
INSERT INTO auto_login.website_schedules (id, account_id, name, code, refresh_interval, schedule_type, schedule_time, schedule_cron, alert_audio_path, is_enabled, created_at, updated_at) VALUES (1, 1, '刷新上架货品', 'refresh_up_goods', -1, 'scheduled', null, '40', 'uploads/audio/81035b19e00b414ca41b31a0d925533b.mp3', 1, '2026-07-07 16:36:04', '2026-07-07 17:07:39');
