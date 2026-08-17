"""Validated machine-to-Wireless-HID binding received from the controller."""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from typing import Any, Mapping


_DEVICE_ID = re.compile(r"^[0-9A-F]{12}$")


@dataclass(frozen=True)
class WirelessHidBinding:
    record_id: int
    device_id: str
    name: str
    host: str
    port: int

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "WirelessHidBinding":
        if not isinstance(payload, Mapping):
            raise ValueError("wireless_hid binding must be an object")

        record_id = payload.get("record_id")
        if isinstance(record_id, bool) or not isinstance(record_id, int) or record_id <= 0:
            raise ValueError("wireless_hid.record_id must be a positive integer")

        device_id = str(payload.get("device_id") or "").strip().upper()
        if not _DEVICE_ID.fullmatch(device_id):
            raise ValueError("wireless_hid.device_id must be 12 uppercase hex digits")

        host = str(payload.get("ip") or "").strip()
        try:
            address = ipaddress.ip_address(host)
        except ValueError as exc:
            raise ValueError("wireless_hid.ip must be a valid IPv4 address") from exc
        if address.version != 4:
            raise ValueError("wireless_hid.ip must be a valid IPv4 address")

        port = payload.get("control_port")
        if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
            raise ValueError("wireless_hid.control_port must be 1..65535")

        return cls(
            record_id=record_id,
            device_id=device_id,
            name=str(payload.get("name") or device_id).strip() or device_id,
            host=host,
            port=port,
        )

