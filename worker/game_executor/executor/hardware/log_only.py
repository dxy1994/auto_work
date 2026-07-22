"""旧导入路径兼容；新代码请使用 ManualActionHardwareController。"""

from game_executor.executor.hardware.manual import ManualActionHardwareController


class LogOnlyHardwareController(ManualActionHardwareController):
    """兼容旧名称，不再包含 DRY_RUN 终态语义。"""

    pass
