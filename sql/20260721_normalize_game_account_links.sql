-- 游戏账号的大区与机器关系分别由关联表维护：
--   game_account_regions(game_account_id, region_id)
--   machine_game_accounts(machine_id, game_account_id)

ALTER TABLE game_accounts
    DROP COLUMN region_id,
    DROP COLUMN machine_id;

ALTER TABLE machine_game_accounts
    DROP INDEX uk_machine_game_account_region,
    DROP INDEX region_id,
    DROP COLUMN region_id,
    ADD UNIQUE INDEX uk_machine_game_account (machine_id, game_account_id);
