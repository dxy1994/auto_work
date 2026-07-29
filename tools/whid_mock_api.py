"""Small mock HTTP API for developing the Wireless HID Vue console.

This does not emulate the wire protocol. It emulates the Spring endpoints used
by the browser UI so the visual and interaction states can be tested without a
database or physical device.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


DEVICE: dict[str, Any] = {
    "id": 1,
    "name": "WirelessHID-5BF8",
    "device_type": "Wireless HID",
    "device_id": "284E4F1B5BF8",
    "ip": "192.168.6.167",
    "control_port": 39667,
    "management_port": 39668,
    "firmware": "0.1.0",
    "claimed": False,
    "ch9329": True,
    "rssi": -25,
    "connection_state": "ready",
    "management_authenticated": False,
    "machine_name": "测试工作站 01",
    "remark": "UI mock device",
    "is_active": 1,
    "last_error": None,
    "last_seen": datetime.now(timezone.utc).isoformat(),
}


class Handler(BaseHTTPRequestHandler):
    server_version = "WHIDMock/1.0"

    def do_GET(self) -> None:
        if self.path in {"/api/orders/manual-alerts", "/api/system-alerts"}:
            self._json(
                {
                    "items": [],
                    "total": 0,
                    "polled_at": datetime.now(timezone.utc).isoformat(),
                }
            )
        elif self.path == "/api/wireless-hid/devices":
            self._json([DEVICE])
        elif self.path == "/api/wireless-hid/1/status":
            self._json(
                {
                    "claimed": True,
                    "ch9329_online": True,
                    "wifi_rssi": -25,
                    "uptime_seconds": 3723,
                    "last_heartbeat_at": datetime.now(timezone.utc).isoformat(),
                }
            )
        elif self.path == "/api/wireless-hid/1/management/status":
            self._json(
                {
                    "device_id": DEVICE["device_id"],
                    "name": DEVICE["name"],
                    "firmware": DEVICE["firmware"],
                    "ip": DEVICE["ip"],
                    "rssi": DEVICE["rssi"],
                    "ch9329": True,
                    "free_heap": 218640,
                    "uptime": 3723,
                }
            )
        else:
            self._json({"detail": "not found"}, 404)

    def do_POST(self) -> None:
        if self.path == "/api/wireless-hid/discover":
            DEVICE["last_seen"] = datetime.now(timezone.utc).isoformat()
            self._json([DEVICE])
        elif self.path == "/api/wireless-hid/1/connect":
            DEVICE["connection_state"] = "connected"
            DEVICE["claimed"] = True
            self._json(DEVICE)
        elif self.path == "/api/wireless-hid/1/disconnect":
            DEVICE["connection_state"] = "ready"
            DEVICE["claimed"] = False
            self._json(DEVICE)
        elif self.path == "/api/wireless-hid/1/management/session":
            DEVICE["management_authenticated"] = True
            self._json(
                {
                    "role": "factory",
                    "valid": True,
                    "expires_at": (
                        datetime.now(timezone.utc) + timedelta(minutes=5)
                    ).isoformat(),
                }
            )
        elif self.path == "/api/wireless-hid/1/management/name":
            body = self._request_json()
            DEVICE["name"] = body.get("name") or DEVICE["name"]
            self._json(DEVICE)
        elif self.path.startswith("/api/wireless-hid/"):
            self._json({"ok": True})
        else:
            self._json({"detail": "not found"}, 404)

    def do_DELETE(self) -> None:
        self._json({"ok": True})

    def log_message(self, format_string: str, *args: Any) -> None:
        return

    def _request_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length))
        except Exception:
            return {}

    def _json(self, value: Any, status: int = 200) -> None:
        payload = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 8000), Handler)
    print("Wireless HID mock API listening on http://127.0.0.1:8000")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
