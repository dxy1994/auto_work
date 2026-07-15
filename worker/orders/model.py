"""Platform-neutral order values sent from Worker to central control."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


@dataclass(frozen=True)
class NormalizedOrder:
    platform: str
    source_order_no: str
    region_external_key: str
    asset_type: str
    asset_amount: Decimal
    buyer_character: str
    platform_status: str







    
    raw_title: str = ""
    game_name: str = ""
    platform_order_time: str = ""
    platform_price: Decimal = Decimal("0")
    platform_item_type: str = ""

    def __post_init__(self):
        for field_name in (
            "platform", "source_order_no", "region_external_key",
            "buyer_character", "platform_status",
        ):
            value = str(getattr(self, field_name) or "").strip()
            if not value:
                raise ValueError(f"{field_name} is required")
            object.__setattr__(self, field_name, value)

        asset_type = str(self.asset_type or "").strip().lower()
        if asset_type != "adena":
            raise ValueError("first phase supports Adena only")
        object.__setattr__(self, "asset_type", asset_type)

        try:
            amount = Decimal(str(self.asset_amount))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("asset_amount must be numeric") from exc
        if not amount.is_finite() or amount <= 0:
            raise ValueError("asset_amount must be positive")
        object.__setattr__(self, "asset_amount", amount)
        object.__setattr__(self, "raw_title", str(self.raw_title or "").strip()[:256])
        object.__setattr__(self, "game_name", str(self.game_name or "").strip()[:100])

    def to_wire(self):
        return {
            "platform": self.platform,
            "source_order_no": self.source_order_no,
            "region_external_key": self.region_external_key,
            "asset_type": self.asset_type,
            "asset_amount": format(self.asset_amount, "f"),
            "buyer_character": self.buyer_character,
            "platform_status": self.platform_status,
            "raw_title": self.raw_title,
            "game_name": self.game_name,
            "platform_order_time": self.platform_order_time or "",
            "platform_price": format(self.platform_price, "f") if self.platform_price else "0",
            "platform_item_type": self.platform_item_type or "",
        }
