"""已停用的统一 Worker 入口。

监控端和游戏执行端必须独立部署，避免在同一进程或同一安装包中混入对方依赖。
"""

import sys


def main() -> int:
    print("统一 Worker 入口已停用。")
    print("监控主机请运行: python -m monitor.main")
    print("游戏执行主机请运行: python -m game_executor.main")
    return 2


if __name__ == "__main__":
    sys.exit(main())
