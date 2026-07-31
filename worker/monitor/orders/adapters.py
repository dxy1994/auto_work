"""Pure adapters for text already extracted from marketplace order rows."""

import re
from decimal import Decimal, InvalidOperation

from .model import NormalizedOrder


_NUMBER = re.compile(r"(?<![\d,])\d+(?:,\d{3})*(?:\.\d+)?")

# 韩语主单位（万/亿/万亿）
_KO_MAJOR = [
    ('조', Decimal('1000000000000')),
    ('억', Decimal('100000000')),
    ('만', Decimal('10000')),
]
# 韩语次单位（千/百/十）
_KO_MINOR = [
    ('천', Decimal('1000')),
    ('백', Decimal('100')),
    ('십', Decimal('10')),
]


def _parse_ko_units(text: str) -> Decimal:
    """
    解析含韩语单位的数字字符串，支持分层结构。
    例: '5천만' → 50000000, '3억5천만' → 350000000
    """
    text = text.replace(' ', '').replace(',', '')
    total = Decimal('0')
    major_acc = Decimal('0')
    minor_acc = Decimal('0')
    i = 0
    while i < len(text):
        ch = text[i]
        if ch.isdigit():
            num_str = ''
            while i < len(text) and text[i].isdigit():
                num_str += text[i]
                i += 1
            minor_acc = Decimal(num_str)
        else:
            matched = False
            for unit_char, multiplier in _KO_MINOR:
                if text[i:i + len(unit_char)] == unit_char:
                    if minor_acc == 0:
                        minor_acc = Decimal('1')
                    major_acc += minor_acc * multiplier
                    minor_acc = Decimal('0')
                    i += len(unit_char)
                    matched = True
                    break
            if not matched:
                for unit_char, multiplier in _KO_MAJOR:
                    if text[i:i + len(unit_char)] == unit_char:
                        section_val = major_acc + minor_acc
                        if section_val == 0:
                            section_val = Decimal('1')
                        total += section_val * multiplier
                        major_acc = Decimal('0')
                        minor_acc = Decimal('0')
                        i += len(unit_char)
                        matched = True
                        break
            if not matched:
                i += 1
    total += major_acc + minor_acc
    return total


def parse_korean_amount(text):
    """
    解析韩语金额文本，支持纯数字和含单位(만/억/조/천/백/십)的混合写法。
    返回 Decimal。
    """
    value = str(text or "").strip().replace('원', '')
    # 始终校验：只能有一个数字部分
    matches = _NUMBER.findall(value)
    if len(matches) != 1:
        raise ValueError("amount text must contain exactly one number")
    # 检测是否包含韩语单位
    has_unit = any(u for u, _ in _KO_MAJOR + _KO_MINOR if u in value)
    if has_unit:
        amount = _parse_ko_units(value)
    else:
        try:
            amount = Decimal(matches[0].replace(",", ""))
        except InvalidOperation as exc:
            raise ValueError("invalid amount") from exc
    if not amount.is_finite() or amount <= 0:
        raise ValueError("amount must be positive")
    return amount


class _Adapter:
    platform = ""
    fields = {}
    ready_statuses = frozenset(("paid", "ready"))

    def __init__(self):
        self._last_reject_reason = ""

    @property
    def last_reject_reason(self) -> str:
        """上上次 normalize() 返回 None 的原因。"""
        return self._last_reject_reason

    def normalize(self, raw, **extra):
        """标准化订单。extra 字段直接穿透到 NormalizedOrder（如 platform_order_time 等）。"""
        try:
            status = self._value(raw, "status").lower()
        except ValueError as e:
            self._last_reject_reason = f"状态字段缺失: {e}"
            return None
        if status not in self.ready_statuses:
            self._last_reject_reason = (
                f"状态 '{status}' 不在允许范围 {set(self.ready_statuses)}")
            return None
        try:
            title = self._value(raw, "title")
        except ValueError as e:
            self._last_reject_reason = f"标题字段缺失: {e}"
            return None
        try:
            asset_type = self._resolve_asset_type(raw)
            return NormalizedOrder(
                platform=self.platform,
                source_order_no=self._value(raw, "order_no"),
                region_external_key=self._value(raw, "region"),
                asset_type=asset_type,
                asset_amount=parse_korean_amount(self._value(raw, "amount")),
                buyer_character=self._value(raw, "buyer"),
                platform_status=status,
                raw_title=title,
                game_name=str(raw.get(self.fields.get("game_name", "game_name")) or "").strip()[:100],
                **extra,
            )
        except (ValueError, KeyError) as e:
            self._last_reject_reason = f"字段校验失败: {e}"
            return None

    def _value(self, raw, semantic_name):
        source_name = self.fields[semantic_name]
        value = str(raw.get(source_name) or "").strip()
        if not value:
            raise ValueError(f"missing {source_name}")
        return value

    def _resolve_asset_type(self, raw) -> str:
        return str(raw.get("item_type") or "").strip() or "unknown"


class ItemmaniaAdapter(_Adapter):
    platform = "itemmania"
    ready_statuses = frozenset(("paid", "ready", "trading"))
    fields = {
        "order_no": "order_no", "region": "server",
        "title": "product_title", "amount": "quantity",
        "buyer": "buyer_name", "status": "state",
        "game_name": "game_name",
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
    ready_statuses = frozenset(("paid", "ready", "trading"))
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
