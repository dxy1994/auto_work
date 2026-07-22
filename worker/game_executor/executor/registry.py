"""游戏交易执行器注册表。只有已注册执行器的游戏才会接受交易指派。"""

from typing import Optional

from game_executor.executor.base import BaseGameExecutor


class ExecutorRegistry:
    def __init__(self):
        self._executors: dict[str, BaseGameExecutor] = {}

    def register(self, executor: BaseGameExecutor):
        aliases = getattr(executor, "game_codes", (executor.game_code,))
        game_codes = {str(code).strip().lower() for code in aliases if str(code).strip()}
        if not game_codes:
            raise ValueError("executor game_code is required")
        duplicates = sorted(code for code in game_codes if code in self._executors)
        if duplicates:
            raise ValueError(f"duplicate executor for game_code={duplicates[0]}")
        for game_code in game_codes:
            self._executors[game_code] = executor

    def get(self, game_code: str) -> Optional[BaseGameExecutor]:
        if not game_code:
            return None
        return self._executors.get(game_code.strip().lower())

    def executors(self) -> tuple[BaseGameExecutor, ...]:
        """返回去重后的执行器；同一游戏的多个别名只检查一次。"""
        results: list[BaseGameExecutor] = []
        seen: set[int] = set()
        for executor in self._executors.values():
            identity = id(executor)
            if identity not in seen:
                seen.add(identity)
                results.append(executor)
        return tuple(results)


EXECUTOR_REGISTRY = ExecutorRegistry()
