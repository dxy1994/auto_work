"""Wireless HID Firmware V1 TCP control SDK used by the game executor.

This is the production control subset of the reference SDK in ``tools/whid_sdk.py``.
It uses only the Python standard library so the game-executor package remains
self-contained when built as an executable.
"""

from __future__ import annotations

import ipaddress
import json
import select
import socket
import struct
import threading
import time
import zlib
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Iterable


DISCOVERY_PORT = 39666
CONTROL_PORT = 39667
DISCOVERY_REQUEST = b"WHID_DISCOVER_V1"
MAGIC = b"WHID"
VERSION = 1
HEADER = struct.Struct("<4sBBHII")
MAX_PAYLOAD = 64


class MessageType(IntEnum):
    CLAIM = 0x01
    RELEASE = 0x02
    HEARTBEAT = 0x03
    GET_STATUS = 0x04
    STATUS = 0x05
    KEYBOARD = 0x10
    MOUSE_REL = 0x11
    MOUSE_ABS = 0x12
    RELEASE_ALL = 0x13
    ACK = 0x70
    ERROR = 0x71


STATUS_NAMES = {
    0: "OK",
    1: "BUSY",
    2: "NOT_CLAIMED",
    3: "INVALID_FRAME",
    4: "INVALID_PAYLOAD",
    5: "HID_UNAVAILABLE",
    6: "UNSUPPORTED",
}


class WirelessHidError(RuntimeError):
    """Base SDK error."""


class ProtocolError(WirelessHidError):
    """The device returned an invalid or unexpected WHID/1 frame."""


class DeviceError(WirelessHidError):
    """The device rejected a valid request."""

    def __init__(self, status: int, request_type: int):
        self.status = int(status)
        self.request_type = int(request_type)
        super().__init__(
            f"device error {STATUS_NAMES.get(status, f'UNKNOWN_{status}')} "
            f"for request 0x{request_type:02X}"
        )


@dataclass(frozen=True)
class DiscoveredDevice:
    device_id: str
    name: str
    ip: str
    control_port: int
    claimed: bool
    ch9329: bool

    @classmethod
    def from_response(cls, payload: bytes, source_ip: str) -> "DiscoveredDevice":
        try:
            data = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProtocolError("discovery response is not UTF-8 JSON") from exc
        if not isinstance(data, dict) or data.get("protocol") != 1:
            raise ProtocolError("unsupported discovery protocol")
        device_id = data.get("id")
        if (
            not isinstance(device_id, str)
            or len(device_id) != 12
            or any(character not in "0123456789ABCDEF" for character in device_id)
        ):
            raise ProtocolError("invalid discovery device id")
        name = data.get("name")
        if not isinstance(name, str) or not name:
            raise ProtocolError("invalid discovery device name")
        control_port = data.get("controlPort")
        if (
            isinstance(control_port, bool)
            or not isinstance(control_port, int)
            or not 1 <= control_port <= 65535
        ):
            raise ProtocolError("invalid discovery control port")
        if not isinstance(data.get("claimed"), bool) or not isinstance(data.get("ch9329"), bool):
            raise ProtocolError("invalid discovery status fields")
        return cls(
            device_id=device_id,
            name=name,
            ip=source_ip,
            control_port=control_port,
            claimed=data["claimed"],
            ch9329=data["ch9329"],
        )


def discover_unicast(host: str, timeout: float = 1.0) -> DiscoveredDevice | None:
    """Discover exactly the device currently answering at a bound IPv4 address."""
    try:
        address = ipaddress.ip_address(host)
    except ValueError as exc:
        raise ValueError("host must be a valid IPv4 address") from exc
    if address.version != 4:
        raise ValueError("host must be a valid IPv4 address")
    if not 0.1 <= float(timeout) <= 5.0:
        raise ValueError("timeout must be between 0.1 and 5 seconds")

    current = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        current.sendto(DISCOVERY_REQUEST, (host, DISCOVERY_PORT))
        current.setblocking(False)
        deadline = time.monotonic() + float(timeout)
        while time.monotonic() < deadline:
            readable, _, _ = select.select(
                [current],
                [],
                [],
                min(0.2, max(0.0, deadline - time.monotonic())),
            )
            if not readable:
                continue
            payload, source = current.recvfrom(2048)
            if source[0] != host:
                continue
            return DiscoveredDevice.from_response(payload, source[0])
        return None
    finally:
        current.close()


@dataclass(frozen=True)
class Frame:
    message_type: MessageType
    sequence: int
    payload: bytes = b""

    def encode(self) -> bytes:
        if len(self.payload) > MAX_PAYLOAD:
            raise ValueError("payload cannot exceed 64 bytes")
        crc = zlib.crc32(self.payload) & 0xFFFFFFFF if self.payload else 0
        return HEADER.pack(
            MAGIC,
            VERSION,
            int(self.message_type),
            len(self.payload),
            self.sequence,
            crc,
        ) + self.payload

    @classmethod
    def read_from(cls, stream: socket.socket) -> "Frame":
        header = _recv_exact(stream, HEADER.size)
        magic, version, raw_type, length, sequence, expected_crc = HEADER.unpack(header)
        if magic != MAGIC:
            raise ProtocolError("frame magic is not WHID")
        if version != VERSION:
            raise ProtocolError(f"unsupported protocol version {version}")
        if length > MAX_PAYLOAD:
            raise ProtocolError(f"payload length {length} exceeds 64")
        try:
            message_type = MessageType(raw_type)
        except ValueError as exc:
            raise ProtocolError(f"unsupported message type 0x{raw_type:02X}") from exc
        payload = _recv_exact(stream, length)
        actual_crc = zlib.crc32(payload) & 0xFFFFFFFF if payload else 0
        if actual_crc != expected_crc:
            raise ProtocolError(
                f"CRC32 mismatch: expected={expected_crc:08x} actual={actual_crc:08x}"
            )
        return cls(message_type, sequence, payload)


class ControlClient:
    """Claimed TCP control connection with serialized requests and heartbeat."""

    def __init__(self, host: str, port: int = CONTROL_PORT):
        if not host or not isinstance(host, str):
            raise ValueError("host is required")
        if not 1 <= int(port) <= 65535:
            raise ValueError("port must be 1..65535")
        self.host = host.strip()
        self.port = int(port)
        self._socket: socket.socket | None = None
        self._sequence = 1
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._heartbeat_thread: threading.Thread | None = None
        self.last_error: str | None = None
        self.last_heartbeat_at: float | None = None

    def connect(self) -> "ControlClient":
        if self.connected:
            return self
        current = socket.create_connection((self.host, self.port), timeout=2.0)
        current.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        current.settimeout(1.5)
        self._socket = current
        try:
            self._request(MessageType.CLAIM, expected={MessageType.ACK})
        except Exception:
            current.close()
            self._socket = None
            raise
        self._stop.clear()
        self.last_error = None
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            name=f"whid-worker-heartbeat-{self.host}",
            daemon=True,
        )
        self._heartbeat_thread.start()
        return self

    @property
    def connected(self) -> bool:
        return self._socket is not None and not self._stop.is_set()

    def status(self) -> dict[str, Any]:
        response = self._request(
            MessageType.GET_STATUS,
            expected={MessageType.STATUS},
        )
        if len(response.payload) != 8:
            raise ProtocolError("STATUS payload must be 8 bytes")
        claimed, online, rssi, reserved, uptime = struct.unpack(
            "<BBbBI",
            response.payload,
        )
        if reserved != 0:
            raise ProtocolError("STATUS reserved byte is not zero")
        return {
            "claimed": bool(claimed),
            "ch9329_online": bool(online),
            "wifi_rssi": int(rssi),
            "uptime_seconds": int(uptime),
            "last_heartbeat_at": self.last_heartbeat_at,
        }

    def keyboard(
        self,
        modifier: int = 0,
        keys: Iterable[int] = (),
        *,
        tap: bool = True,
    ) -> None:
        usages = [int(value) for value in keys]
        if not 0 <= int(modifier) <= 255 or len(usages) > 6:
            raise ValueError("modifier must be uint8 and keys may contain at most 6 usages")
        if any(not 0 <= usage <= 255 for usage in usages):
            raise ValueError("usage ids must be uint8")
        payload = bytes([
            int(modifier),
            0,
            *usages,
            *([0] * (6 - len(usages))),
        ])
        self._request(MessageType.KEYBOARD, payload, expected={MessageType.ACK})
        if tap:
            self._request(MessageType.KEYBOARD, bytes(8), expected={MessageType.ACK})

    def mouse_relative(
        self,
        buttons: int = 0,
        x: int = 0,
        y: int = 0,
        wheel: int = 0,
    ) -> None:
        if not 0 <= int(buttons) <= 7:
            raise ValueError("buttons must be 0..7")
        if not all(-128 <= int(value) <= 127 for value in (x, y, wheel)):
            raise ValueError("relative x/y/wheel must be -128..127")
        self._request(
            MessageType.MOUSE_REL,
            struct.pack("<Bbbb", int(buttons), int(x), int(y), int(wheel)),
            expected={MessageType.ACK},
        )

    def mouse_absolute(
        self,
        buttons: int = 0,
        x: int = 0,
        y: int = 0,
        wheel: int = 0,
    ) -> None:
        if not 0 <= int(buttons) <= 7:
            raise ValueError("buttons must be 0..7")
        if not 0 <= int(x) <= 4095 or not 0 <= int(y) <= 4095:
            raise ValueError("absolute x/y must be 0..4095")
        if not -128 <= int(wheel) <= 127:
            raise ValueError("wheel must be -128..127")
        self._request(
            MessageType.MOUSE_ABS,
            struct.pack("<BHHb", int(buttons), int(x), int(y), int(wheel)),
            expected={MessageType.ACK},
        )

    def release_all(self) -> None:
        self._request(MessageType.RELEASE_ALL, expected={MessageType.ACK})

    def close(self) -> None:
        current = self._socket
        if current is None:
            self._stop.set()
            return
        failure: Exception | None = None
        try:
            self.release_all()
            self._request(MessageType.RELEASE, expected={MessageType.ACK})
        except Exception as exc:
            failure = exc
        finally:
            self._stop.set()
            try:
                current.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            current.close()
            self._socket = None
        if failure:
            raise failure

    def _request(
        self,
        message_type: MessageType,
        payload: bytes = b"",
        expected: set[MessageType] | None = None,
    ) -> Frame:
        current = self._socket
        if current is None:
            raise WirelessHidError("control connection is not open")
        with self._lock:
            sequence = self._sequence
            self._sequence = (self._sequence + 1) & 0xFFFFFFFF or 1
            current.sendall(Frame(message_type, sequence, payload).encode())
            response = Frame.read_from(current)
        if response.sequence != sequence:
            raise ProtocolError(
                f"sequence mismatch expected={sequence} actual={response.sequence}"
            )
        if response.message_type == MessageType.ERROR:
            _validate_ack(response.payload, message_type)
        allowed = expected or {MessageType.ACK}
        if response.message_type not in allowed:
            raise ProtocolError(
                f"unexpected response {response.message_type.name} "
                f"for {message_type.name}"
            )
        if response.message_type == MessageType.ACK:
            _validate_ack(response.payload, message_type)
        return response

    def _heartbeat_loop(self) -> None:
        while not self._stop.wait(1.0):
            try:
                self._request(
                    MessageType.HEARTBEAT,
                    expected={MessageType.HEARTBEAT},
                )
                self.last_heartbeat_at = time.time()
            except Exception as exc:
                self.last_error = str(exc)
                self._stop.set()
                current = self._socket
                self._socket = None
                if current is not None:
                    try:
                        current.close()
                    except OSError:
                        pass
                return


def ascii_keystroke(character: str) -> tuple[int, int]:
    """Map one US-keyboard ASCII character to modifier and Usage ID."""
    if len(character) != 1:
        raise ValueError("one character required")
    if "a" <= character <= "z":
        return 0, 0x04 + ord(character) - ord("a")
    if "A" <= character <= "Z":
        return 0x02, 0x04 + ord(character) - ord("A")

    digits = "1234567890"
    shifted = "!@#$%^&*()"
    if character in digits:
        return 0, 0x1E + digits.index(character)
    if character in shifted:
        return 0x02, 0x1E + shifted.index(character)

    fixed = {
        "\n": (0, 0x28),
        "\r": (0, 0x28),
        "\t": (0, 0x2B),
        " ": (0, 0x2C),
    }
    if character in fixed:
        return fixed[character]

    pairs = [
        ("-", "_", 0x2D),
        ("=", "+", 0x2E),
        ("[", "{", 0x2F),
        ("]", "}", 0x30),
        ("\\", "|", 0x31),
        (";", ":", 0x33),
        ("'", '"', 0x34),
        ("`", "~", 0x35),
        (",", "<", 0x36),
        (".", ">", 0x37),
        ("/", "?", 0x38),
    ]
    for normal, shifted_character, usage in pairs:
        if character == normal:
            return 0, usage
        if character == shifted_character:
            return 0x02, usage
    raise ValueError(f"unsupported character U+{ord(character):04X}")


def _recv_exact(stream: socket.socket, length: int) -> bytes:
    chunks: list[bytes] = []
    remaining = int(length)
    while remaining:
        chunk = stream.recv(remaining)
        if not chunk:
            raise ProtocolError("connection closed before a complete frame was read")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _validate_ack(payload: bytes, request_type: MessageType) -> None:
    if len(payload) != 4:
        raise ProtocolError("ACK/ERROR payload must be 4 bytes")
    actual_request, status, reserved = struct.unpack("<BBH", payload)
    if actual_request != int(request_type) or reserved != 0:
        raise ProtocolError("invalid ACK/ERROR payload")
    if status:
        raise DeviceError(status, actual_request)
