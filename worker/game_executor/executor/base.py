"""
游戏交易执行器抽象基类。

每个游戏实现一个子类，覆写 execute() 方法，
通过统一输入层发送动作，底层设备适配器可在硬件安装包到位后替换。
"""
from abc import ABC, abstractmethod
from typing import Optional

from game_executor.executor.hardware.humanized import InputDeviceAdapter


class BaseGameExecutor(ABC):
    """游戏交易执行器基类。"""

    def __init__(self, hw: InputDeviceAdapter):
        self._hw = hw

    @property
    @abstractmethod
    def game_code(self) -> str:
        """返回游戏标识码（与 game 表的 code 字段对应）。"""
        ...

    @abstractmethod
    async def execute(self, order: dict) -> dict:
        """执行游戏内交易流程。

        Args:
            order: 总控下发的订单数据，包含：
                - order_id: 订单ID
                - game_id: 游戏ID
                - game_account_id: 本次指派使用的游戏账号ID
                - trade_timeout_seconds: 等待买家交易申请的超时秒数
                - region_id: 大区ID
                - region_name: 大区显示名称
                - region_code: 游戏客户端使用的大区代码/名称
                - region_sort_order: 大区在客户端服务器列表中的固定排序号
                - region_select_page: 大区在客户端服务器列表中的页码，从 1 开始
                - region_select_x: 可选，大区在 800x600 客户区中的点击 X 坐标
                - region_select_y: 可选，大区在 800x600 客户区中的点击 Y 坐标
                - buyer_character: 买家角色名
                - asset_type: 资产类型
                - asset_amount: 资产数量
                - details: 子订单明细列表，未选中/选中 recognition_image_*_url 至少提供一张
                - item_positions: 物品在游戏中的位置坐标 [{item_id, x, y, image_url}]

        Returns:
            {"success": bool, "message": str, "duration_ms": int}
        """
        ...

    def cancel(self):
        """取消当前交易（可覆写）。"""
        pass
