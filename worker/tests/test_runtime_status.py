import unittest

from trade.runtime_status import RuntimeStatus


class RuntimeStatusTest(unittest.TestCase):

    def test_snapshot_is_copy_and_uses_protocol_keys(self):
        status = RuntimeStatus()
        status.update(
            game_id=3,
            game_account_id=27,
            region_id=8,
            client_status="logged_in",
            character_name="테스터",
            executor_status="idle",
            ui_health="ready",
        )

        snapshot = status.snapshot()
        snapshot["executor_status"] = "busy"

        self.assertEqual("idle", status.snapshot()["executor_status"])
        self.assertIsNone(status.snapshot()["current_assignment_id"])

    def test_update_rejects_unknown_protocol_field(self):
        status = RuntimeStatus()

        with self.assertRaisesRegex(ValueError, "unknown runtime fields"):
            status.update(unexpected="value")


if __name__ == "__main__":
    unittest.main()
