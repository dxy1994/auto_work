"""Pure adapters for text already extracted from marketplace order rows."""

import re
from decimal import Decimal, InvalidOperation

from .model import NormalizedOrder


_NUMBER = re.compile(r"(?<![\d,])\d+(?:,\d{3})*(?:\.\d+)?")


def parse_korean_amount(text):
    value = str(text or "").strip()
    matches = _NUMBER.findall(value)
    if len(matches) != 1:
        raise ValueError("amount text must contain exactly one number")
    try:
        amount = Decimal(matches[0].replace(",", ""))
    except InvalidOperation as exc:
        raise ValueError("invalid amount") from exc
    if "만" in value:
        amount *= Decimal("10000")
    if not amount.is_finite() or amount <= 0:
        raise ValueError("amount must be positive")
    return amount


class _Adapter:
    platform = ""
    fields = {}
    ready_statuses = frozenset(("paid", "ready"))

    def normalize(self, raw):
        status = self._value(raw, "status").lower()
        if status not in self.ready_statuses:
            return None
        title = self._value(raw, "title")
        lowered_title = title.lower()
        if "아덴" not in title and "adena" not in lowered_title:
            return None
        return NormalizedOrder(
            platform=self.platform,
            source_order_no=self._value(raw, "order_no"),
            region_external_key=self._value(raw, "region"),
            asset_type="adena",
            asset_amount=parse_korean_amount(self._value(raw, "amount")),
            buyer_character=self._value(raw, "buyer"),
            platform_status=status,
            raw_title=title,
        )

    def _value(self, raw, semantic_name):
        source_name = self.fields[semantic_name]
        value = str(raw.get(source_name) or "").strip()
        if not value:
            raise ValueError(f"missing {source_name}")
        return value


class ItemmaniaAdapter(_Adapter):
    platform = "itemmania"
    fields = {
        "order_no": "order_no", "region": "server",
        "title": "product_title", "amount": "quantity",
        "buyer": "buyer_name", "status": "state",
    }


class BarotemAdapter(_Adapter):
    platform = "barotem"
    fields = {
        "order_no": "deal_id", "region": "server_code",
        "title": "item_name", "amount": "amount",
        "buyer": "buyer_character", "status": "status",
    }


class ItembayAdapter(_Adapter):
    platform = "itembay"
    fields = {
        "order_no": "item_order_no", "region": "server_id",
        "title": "title", "amount": "trade_amount",
        "buyer": "character", "status": "trade_status",
    }


_ADAPTERS = {
    "itemmania": ItemmaniaAdapter(),
    "barotem": BarotemAdapter(),
    "itembay": ItembayAdapter(),
}


def adapter_for(platform):
    try:
        return _ADAPTERS[str(platform).strip().lower()]
    except KeyError as exc:
        raise ValueError(f"unsupported marketplace: {platform}") from exc
