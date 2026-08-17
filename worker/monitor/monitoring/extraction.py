"""订单表格提取结果，显式区分“正常空表”和“提取失败”。"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class OrderExtractionResult:
    orders: list = field(default_factory=list)
    error: Optional[str] = None

    @property
    def failed(self) -> bool:
        return self.error is not None

    @classmethod
    def success(cls, orders=None):
        return cls(orders=list(orders or []))

    @classmethod
    def failure(cls, error: str):
        return cls(error=error or "未知提取错误")
