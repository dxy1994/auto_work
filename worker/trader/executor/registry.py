"""游戏交易执行器注册表。只有已注册执行器的游戏才会接受交易指派。"""

from typing import Optional

from trader.executor.base import BaseGameExecutor


class ExecutorRegistry:
    def __init__(self):
        self._executors: dict[str, BaseGameExecutor] = {}

    def register(self, executor: BaseGameExecutor):
        game_code = executor.game_code.strip().lower()
        if not game_code:
            raise ValueError("executor game_code is required")
        if game_code in self._executors:
            raise ValueError(f"duplicate executor for game_code={game_code}")
        self._executors[game_code] = executor

    def get(self, game_code: str) -> Optional[BaseGameExecutor]:
        if not game_code:
            return None
        return self._executors.get(game_code.strip().lower())


EXECUTOR_REGISTRY = ExecutorRegistry()
