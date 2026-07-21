import ast
import unittest
from pathlib import Path


WORKER_ROOT = Path(__file__).resolve().parent.parent


def imported_roots(package: str) -> set[str]:
    roots: set[str] = set()
    for path in (WORKER_ROOT / package).rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                roots.add(node.module.split(".", 1)[0])
    return roots


class WorkerBoundaryTest(unittest.TestCase):
    def test_common_has_no_role_dependency(self):
        imports = imported_roots("common")
        self.assertNotIn("monitor", imports)
        self.assertNotIn("game_executor", imports)

    def test_monitor_does_not_import_game_executor(self):
        self.assertNotIn("game_executor", imported_roots("monitor"))

    def test_game_executor_does_not_import_monitor(self):
        self.assertNotIn("monitor", imported_roots("game_executor"))

    def test_production_requirements_are_role_specific(self):
        monitor = (WORKER_ROOT / "requirements-monitor.txt").read_text("utf-8")
        executor = (WORKER_ROOT / "requirements-game-executor.txt").read_text("utf-8")
        self.assertNotIn("paddleocr", monitor.casefold())
        self.assertNotIn("patchright", executor.casefold())


if __name__ == "__main__":
    unittest.main()
