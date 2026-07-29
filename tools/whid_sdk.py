"""Wireless HID Firmware V1 reference SDK.

This module intentionally uses only the Python standard library so it can be
copied to a Windows/Linux test machine without installing packages.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import select
import socket
import struct
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zlib
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import Any, Iterable


DISCOVERY_PORT = 39666
CONTROL_PORT = 39667
MANAGEMENT_PORT = 39668
DISCOVERY_REQUEST = b"WHID_DISCOVER_V1"
MAGIC = b"WHID"
VERSION = 1
HEADER = struct.Struct("<4sBBHII")
MAX_PAYLOAD = 64
MAX_FIRMWARE_SIZE = 0x180000


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
    """Malformed frame or unexpected device response."""


class DeviceError(WirelessHidError):
    """ERROR/ACK status returned by the device."""

    def __init__(self, status: int, request_type: int):
        self.status = status
        self.request_type = request_type
        super().__init__(
            f"device error {STATUS_NAMES.get(status, f'UNKNOWN_{status}')} "
            f"for request 0x{request_type:02X}"
        )


class ManagementError(WirelessHidError):
    """Non-success HTTP management response."""

    def __init__(self, status: int, error: str):
        self.status = status
        self.error = error
        super().__init__(f"management HTTP {status}: {error}")


@dataclass(frozen=True)
class Frame:
    message_type: MessageType
    sequence: int
    payload: bytes = b""

    def encode(self) -> bytes:
        if len(self.payload) > MAX_PAYLOAD:
            raise ValueError("payload cannot exceed 64 bytes")
        if not 0 <= self.sequence <= 0xFFFFFFFF:
            raise ValueError("sequence must be uint32")
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


@dataclass(frozen=True)
class DiscoveredDevice:
    protocol: int
    id: str
    name: str
    ip: str
    control_port: int
    management_port: int
    firmware: str
    claimed: bool
    ch9329: bool
    rssi: int

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
            or any(ch not in "0123456789ABCDEF" for ch in device_id)
        ):
            raise ProtocolError("invalid device id")
        name = data.get("name")
        firmware = data.get("firmware")
        if not isinstance(name, str) or not name or len(name) > 96:
            raise ProtocolError("invalid device name")
        if not isinstance(firmware, str) or not firmware or len(firmware) > 32:
            raise ProtocolError("invalid firmware version")
        control_port = _validate_port(data.get("controlPort"), "controlPort")
        management_port = _validate_port(data.get("managementPort"), "managementPort")
        if not isinstance(data.get("claimed"), bool) or not isinstance(data.get("ch9329"), bool):
            raise ProtocolError("invalid boolean discovery fields")
        rssi = data.get("rssi")
        if not isinstance(rssi, int) or not -127 <= rssi <= 0:
            raise ProtocolError("invalid RSSI")
        reported_ip = data.get("ip")
        ip = reported_ip if _is_ipv4(reported_ip) and reported_ip == source_ip else source_ip
        return cls(
            protocol=1,
            id=device_id,
            name=name,
            ip=ip,
            control_port=control_port,
            management_port=management_port,
            firmware=firmware,
            claimed=data["claimed"],
            ch9329=data["ch9329"],
            rssi=rssi,
        )


def discover(timeout: float = 1.5, ip: str | None = None) -> list[DiscoveredDevice]:
    """Discover all devices, or unicast discovery to a known IPv4 address."""
    if not 0.1 <= timeout <= 5.0:
        raise ValueError("timeout must be between 0.1 and 5 seconds")
    if ip and not _is_ipv4(ip):
        raise ValueError("ip must be a valid IPv4 address")

    targets = [(None, ip)] if ip else [(local, "255.255.255.255") for local in _local_ipv4s()]
    sockets: list[socket.socket] = []
    for local, target in targets or [(None, "255.255.255.255")]:
        current = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        current.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        try:
            current.bind((local or "", 0))
            current.sendto(DISCOVERY_REQUEST, (target, DISCOVERY_PORT))
            current.setblocking(False)
            sockets.append(current)
        except OSError:
            current.close()

    deadline = time.monotonic() + timeout
    by_id: dict[str, DiscoveredDevice] = {}
    try:
        while sockets and time.monotonic() < deadline:
            readable, _, _ = select.select(sockets, [], [], min(0.2, deadline - time.monotonic()))
            for current in readable:
                try:
                    payload, address = current.recvfrom(2048)
                    device = DiscoveredDevice.from_response(payload, address[0])
                    by_id[device.id] = device
                except (OSError, WirelessHidError):
                    continue
    finally:
        for current in sockets:
            current.close()
    return list(by_id.values())


class ControlClient:
    """One claimed TCP control connection with an independent heartbeat thread."""

    def __init__(self, host: str, port: int = CONTROL_PORT):
        if not _is_ipv4(host):
            raise ValueError("host must be an IPv4 address")
        self.host = host
        self.port = _validate_port(port, "port")
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
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            name=f"whid-heartbeat-{self.host}",
            daemon=True,
        )
        self._heartbeat_thread.start()
        return self

    @property
    def connected(self) -> bool:
        return self._socket is not None and not self._stop.is_set()

    def status(self) -> dict[str, Any]:
        response = self._request(MessageType.GET_STATUS, expected={MessageType.STATUS})
        if len(response.payload) != 8:
            raise ProtocolError("STATUS payload must be 8 bytes")
        claimed, online, rssi, reserved, uptime = struct.unpack("<BBbBI", response.payload)
        if reserved != 0:
            raise ProtocolError("STATUS reserved byte is not zero")
        return {
            "claimed": bool(claimed),
            "ch9329_online": bool(online),
            "wifi_rssi": rssi,
            "uptime_seconds": uptime,
        }

    def keyboard(self, modifier: int = 0, keys: Iterable[int] = (), tap: bool = True) -> None:
        usages = list(keys)
        if not 0 <= modifier <= 255 or len(usages) > 6:
            raise ValueError("modifier must be uint8 and keys may contain at most 6 usages")
        if any(not 0 <= usage <= 255 for usage in usages):
            raise ValueError("usage ids must be uint8")
        payload = bytes([modifier, 0, *usages, *([0] * (6 - len(usages)))])
        self._request(MessageType.KEYBOARD, payload, expected={MessageType.ACK})
        if tap:
            self._request(MessageType.KEYBOARD, bytes(8), expected={MessageType.ACK})

    def type_text(self, text: str, delay: float = 0.02) -> None:
        if not text or len(text) > 500:
            raise ValueError("text length must be 1..500")
        try:
            for character in text:
                modifier, usage = ascii_keystroke(character)
                self.keyboard(modifier, [usage], tap=True)
                if delay:
                    time.sleep(delay)
        except Exception:
            try:
                self.release_all()
            finally:
                raise

    def mouse_relative(self, buttons: int = 0, x: int = 0, y: int = 0, wheel: int = 0) -> None:
        if not 0 <= buttons <= 7 or not all(-128 <= value <= 127 for value in (x, y, wheel)):
            raise ValueError("invalid relative mouse values")
        self._request(
            MessageType.MOUSE_REL,
            struct.pack("<Bbbb", buttons, x, y, wheel),
            expected={MessageType.ACK},
        )

    def mouse_absolute(self, buttons: int = 0, x: int = 0, y: int = 0, wheel: int = 0) -> None:
        if not 0 <= buttons <= 7 or not 0 <= x <= 4095 or not 0 <= y <= 4095:
            raise ValueError("absolute x/y must be 0..4095 and buttons 0..7")
        if not -128 <= wheel <= 127:
            raise ValueError("wheel must be -128..127")
        self._request(
            MessageType.MOUSE_ABS,
            struct.pack("<BHHb", buttons, x, y, wheel),
            expected={MessageType.ACK},
        )

    def release_all(self) -> None:
        self._request(MessageType.RELEASE_ALL, expected={MessageType.ACK})

    def close(self) -> None:
        self._stop.set()
        current = self._socket
        if current is None:
            return
        failure: Exception | None = None
        try:
            self.release_all()
            self._request(MessageType.RELEASE, expected={MessageType.ACK})
        except Exception as exc:
            failure = exc
        finally:
            current.close()
            self._socket = None
        if failure:
            raise failure

    def __enter__(self) -> "ControlClient":
        return self.connect()

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        try:
            self.close()
        except Exception:
            if exc is None:
                raise

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
        if response.message_type is MessageType.ERROR:
            _validate_ack(response.payload, message_type)
        if expected and response.message_type not in expected:
            raise ProtocolError(
                f"unexpected response {response.message_type.name}, "
                f"expected {[item.name for item in expected]}"
            )
        if response.message_type is MessageType.ACK:
            _validate_ack(response.payload, message_type)
        return response

    def _heartbeat_loop(self) -> None:
        while not self._stop.wait(1.0):
            try:
                self._request(MessageType.HEARTBEAT, expected={MessageType.HEARTBEAT})
                self.last_heartbeat_at = time.time()
            except Exception as exc:
                self.last_error = str(exc)
                self._stop.set()
                if self._socket:
                    self._socket.close()
                    self._socket = None
                return


class ManagementClient:
    """HMAC-authenticated management client. Token is retained in memory only."""

    def __init__(
        self,
        host: str,
        device_id: str,
        port: int = MANAGEMENT_PORT,
        timeout: float = 15.0,
    ):
        if not _is_ipv4(host):
            raise ValueError("host must be an IPv4 address")
        if len(device_id) != 12:
            raise ValueError("device_id must be 12 characters")
        self.host = host
        self.device_id = device_id
        self.port = _validate_port(port, "port")
        self.timeout = timeout
        self.token: str | None = None
        self.role: str | None = None

    def authenticate(self, pin: str) -> dict[str, Any]:
        challenge = self._json_request("GET", "/api/auth/challenge")
        if challenge.get("deviceId") != self.device_id:
            raise ProtocolError("challenge device id does not match discovery result")
        challenge_hex = challenge.get("challenge")
        if (
            challenge.get("algorithm") != "HMAC-SHA256"
            or not isinstance(challenge_hex, str)
            or len(challenge_hex) != 32
        ):
            raise ProtocolError("invalid authentication challenge")
        verifier = hashlib.sha256(f"{self.device_id}:{pin}".encode("utf-8")).digest()
        proof = hmac.new(
            verifier,
            f"{self.device_id}:{challenge_hex}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        session = self._json_request(
            "POST",
            "/api/auth/session",
            urllib.parse.urlencode({"proof": proof}).encode(),
            {"Content-Type": "application/x-www-form-urlencoded"},
        )
        token = session.get("token")
        if not isinstance(token, str) or len(token) != 64:
            raise ProtocolError("invalid management token")
        self.token = token
        self.role = session.get("role")
        return {"role": self.role, "expires_in": session.get("expiresIn")}

    def status(self) -> dict[str, Any]:
        return self._protected("GET", "/api/status")

    def rename(self, name: str) -> dict[str, Any]:
        if not 1 <= len(name.encode("utf-8")) <= 32:
            raise ValueError("name UTF-8 length must be 1..32 bytes")
        return self._protected(
            "POST",
            "/api/device/name",
            urllib.parse.urlencode({"name": name.strip()}).encode(),
        )

    def ota(self, firmware_path: str | Path) -> dict[str, Any]:
        path = Path(firmware_path)
        firmware = path.read_bytes()
        validate_firmware(firmware)
        digest = hashlib.sha256(firmware).hexdigest()
        boundary = f"----WHID{uuid.uuid4().hex}"
        prefix = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
            "Content-Type: application/octet-stream\r\n\r\n"
        ).encode()
        body = prefix + firmware + f"\r\n--{boundary}--\r\n".encode()
        response = self._protected(
            "POST",
            "/api/ota",
            body,
            {
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "X-WHID-SHA256": digest,
            },
            timeout=180.0,
        )
        return {"sha256": digest, "size": len(firmware), "response": response}

    def _protected(
        self,
        method: str,
        path: str,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        if not self.token:
            raise WirelessHidError("management session is not authenticated")
        request_headers = {"X-WHID-Token": self.token}
        if method == "POST":
            request_headers["Content-Type"] = "application/x-www-form-urlencoded"
        request_headers.update(headers or {})
        return self._json_request(method, path, body, request_headers, timeout)

    def _json_request(
        self,
        method: str,
        path: str,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        request = urllib.request.Request(
            f"http://{self.host}:{self.port}{path}",
            data=body,
            method=method,
            headers=headers or {},
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout or self.timeout) as response:
                payload = response.read()
        except urllib.error.HTTPError as exc:
            try:
                error = json.loads(exc.read().decode()).get("error", f"http_{exc.code}")
            except Exception:
                error = f"http_{exc.code}"
            raise ManagementError(exc.code, error) from exc
        try:
            result = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProtocolError("management response is not UTF-8 JSON") from exc
        if not isinstance(result, dict):
            raise ProtocolError("management response must be a JSON object")
        return result


def validate_firmware(firmware: bytes) -> None:
    if not firmware:
        raise ValueError("firmware is empty")
    if len(firmware) > MAX_FIRMWARE_SIZE:
        raise ValueError("firmware exceeds 0x180000 bytes")
    if firmware[0] != 0xE9:
        raise ValueError("firmware does not start with ESP image magic 0xE9")


def ascii_keystroke(character: str) -> tuple[int, int]:
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
    for normal, shifted_char, usage in pairs:
        if character == normal:
            return 0, usage
        if character == shifted_char:
            return 0x02, usage
    raise ValueError(f"unsupported character U+{ord(character):04X}")


def _recv_exact(stream: socket.socket, length: int) -> bytes:
    chunks: list[bytes] = []
    remaining = length
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


def _validate_port(value: Any, name: str) -> int:
    if not isinstance(value, int) or not 1 <= value <= 65535:
        raise ProtocolError(f"invalid {name}")
    return value


def _is_ipv4(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        socket.inet_aton(value)
    except OSError:
        return False
    return value.count(".") == 3


def _local_ipv4s() -> list[str]:
    addresses: set[str] = set()
    try:
        import psutil  # type: ignore[import-not-found]

        for entries in psutil.net_if_addrs().values():
            for entry in entries:
                if entry.family == socket.AF_INET and not entry.address.startswith("127."):
                    addresses.add(entry.address)
    except ImportError:
        pass
    try:
        for entry in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            address = entry[4][0]
            if not address.startswith("127."):
                addresses.add(address)
    except OSError:
        pass
    return sorted(addresses)
