import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


WORKER_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKER_ROOT))

from common.runtime_paths import monitor_user_data_root


class MonitorRuntimePathsTest(unittest.TestCase):
    def test_frozen_exe_uses_persistent_sibling_user_data(self):
        executable = Path("D:/apps/auto-monitor/auto-monitor.exe")
        with patch.object(sys, "frozen", True, create=True), \
                patch.object(sys, "executable", str(executable)), \
                patch.dict(os.environ, {"MONITOR_USER_DATA_DIR": ""}):
            self.assertEqual(
                executable.resolve().parent / "user_data",
                monitor_user_data_root())

    def test_explicit_data_directory_has_priority(self):
        configured = "D:/persistent/monitor-profiles"
        with patch.dict(os.environ, {"MONITOR_USER_DATA_DIR": configured}):
            self.assertEqual(Path(configured).resolve(), monitor_user_data_root())

    def test_monitor_build_preserves_runtime_directory_without_migrating_profiles(self):
        script = (WORKER_ROOT.parent / "scripts" / "build-monitor-exe.bat").read_text(
            encoding="utf-8")
        self.assertNotIn('rmdir /s /q "%DIST_DIR%"', script)
        self.assertNotIn('xcopy "%WORKER_DIR%\\user_data"', script)
        self.assertIn('"%DIST_DIR%\\.env"', script)


if __name__ == "__main__":
    unittest.main()
