"""Command-line smoke tests for Wireless HID Firmware V1.

PINs are requested interactively and are intentionally not accepted as command
line arguments.
"""

from __future__ import annotations

import argparse
import getpass
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from whid_sdk import ControlClient, ManagementClient, WirelessHidError, discover


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Wireless HID V1 protocol test tool")
    subparsers = parser.add_subparsers(dest="command", required=True)

    discover_parser = subparsers.add_parser("discover", help="discover devices over UDP")
    discover_parser.add_argument("--ip", help="known device IPv4 for unicast discovery")
    discover_parser.add_argument("--timeout", type=float, default=1.5)

    status_parser = subparsers.add_parser("status", help="claim TCP control and read status")
    status_parser.add_argument("--ip", required=True)
    status_parser.add_argument("--port", type=int, default=39667)

    keyboard_parser = subparsers.add_parser("keyboard", help="send one HID keyboard report")
    keyboard_parser.add_argument("--ip", required=True)
    keyboard_parser.add_argument("--port", type=int, default=39667)
    keyboard_parser.add_argument("--modifier", type=_integer, default=0)
    keyboard_parser.add_argument("--keys", type=_integer, nargs="*", default=[])

    type_parser = subparsers.add_parser("type", help="type common ASCII text")
    type_parser.add_argument("--ip", required=True)
    type_parser.add_argument("--port", type=int, default=39667)
    type_parser.add_argument("--text", required=True)
    type_parser.add_argument("--delay-ms", type=int, default=20)

    relative_parser = subparsers.add_parser("mouse-rel", help="send relative mouse input")
    relative_parser.add_argument("--ip", required=True)
    relative_parser.add_argument("--port", type=int, default=39667)
    relative_parser.add_argument("--buttons", type=int, default=0)
    relative_parser.add_argument("--x", type=int, default=0)
    relative_parser.add_argument("--y", type=int, default=0)
    relative_parser.add_argument("--wheel", type=int, default=0)

    absolute_parser = subparsers.add_parser("mouse-abs", help="send absolute mouse input")
    absolute_parser.add_argument("--ip", required=True)
    absolute_parser.add_argument("--port", type=int, default=39667)
    absolute_parser.add_argument("--buttons", type=int, default=0)
    absolute_parser.add_argument("--x", type=int, required=True)
    absolute_parser.add_argument("--y", type=int, required=True)
    absolute_parser.add_argument("--wheel", type=int, default=0)

    management_parser = subparsers.add_parser(
        "management-status",
        help="authenticate and read HTTP management status",
    )
    management_parser.add_argument("--ip", required=True)

    rename_parser = subparsers.add_parser("rename", help="authenticate and rename a device")
    rename_parser.add_argument("--ip", required=True)
    rename_parser.add_argument("--name", required=True)

    ota_parser = subparsers.add_parser("ota", help="authenticate and upload firmware")
    ota_parser.add_argument("--ip", required=True)
    ota_parser.add_argument("--file", required=True, type=Path)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "discover":
            _print([asdict(item) for item in discover(args.timeout, args.ip)])
            return 0

        if args.command in {"status", "keyboard", "type", "mouse-rel", "mouse-abs"}:
            with ControlClient(args.ip, args.port) as client:
                if args.command == "status":
                    _print(client.status())
                elif args.command == "keyboard":
                    client.keyboard(args.modifier, args.keys, tap=True)
                    _print({"ok": True, "action": "keyboard"})
                elif args.command == "type":
                    client.type_text(args.text, args.delay_ms / 1000)
                    _print({"ok": True, "action": "type", "characters": len(args.text)})
                elif args.command == "mouse-rel":
                    client.mouse_relative(args.buttons, args.x, args.y, args.wheel)
                    _print({"ok": True, "action": "mouse-rel"})
                else:
                    client.mouse_absolute(args.buttons, args.x, args.y, args.wheel)
                    _print({"ok": True, "action": "mouse-abs"})
            return 0

        device = _resolve_device(args.ip)
        pin = getpass.getpass("管理 PIN / 出厂凭据: ")
        client = ManagementClient(
            device.ip,
            device.id,
            device.management_port,
        )
        session = client.authenticate(pin)
        pin = "\0" * len(pin)
        if args.command == "management-status":
            _print({"session": session, "status": client.status()})
        elif args.command == "rename":
            _print({"session": session, "response": client.rename(args.name)})
        elif args.command == "ota":
            answer = input(
                f"即将升级 {device.name} ({device.id})，输入设备 ID 继续: "
            ).strip()
            if answer != device.id:
                raise WirelessHidError("设备 ID 不匹配，已取消 OTA")
            _print({"session": session, "ota": client.ota(args.file)})
        return 0
    except (WirelessHidError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


def _resolve_device(ip: str):
    devices = discover(timeout=1.5, ip=ip)
    if not devices:
        raise WirelessHidError(f"{ip} 没有返回有效的 UDP 发现响应")
    return devices[0]


def _integer(value: str) -> int:
    return int(value, 0)


def _print(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
