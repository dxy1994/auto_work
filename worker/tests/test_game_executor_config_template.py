import re
import unittest
from pathlib import Path


WORKER_ROOT = Path(__file__).resolve().parents[1]
ENV_KEY_PATTERN = re.compile(r"os\.getenv\(\s*[\"']([A-Z][A-Z0-9_]*)[\"']")
TEMPLATE_KEY_PATTERN = re.compile(r"^\s*([A-Z][A-Z0-9_]*)\s*=", re.MULTILINE)


class GameExecutorConfigTemplateTest(unittest.TestCase):
    def test_template_contains_every_game_executor_environment_setting(self):
        runtime_sources = [
            WORKER_ROOT / "common" / "config.py",
            WORKER_ROOT / "game_executor" / "config.py",
            WORKER_ROOT
            / "game_executor"
            / "executor"
            / "lineage_classic"
            / "navigation.py",
        ]
        runtime_keys = set()
        for source in runtime_sources:
            runtime_keys.update(
                ENV_KEY_PATTERN.findall(source.read_text(encoding="utf-8"))
            )

        template = (
            WORKER_ROOT / ".env.game-executor.example"
        ).read_text(encoding="utf-8")
        template_keys = set(TEMPLATE_KEY_PATTERN.findall(template))

        self.assertEqual(
            set(),
            runtime_keys - template_keys,
            "游戏执行端配置模板缺少运行时环境变量",
        )


if __name__ == "__main__":
    unittest.main()
