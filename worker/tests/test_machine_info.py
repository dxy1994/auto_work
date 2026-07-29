import unittest
from unittest.mock import patch

from common import config


class MachineInfoTest(unittest.TestCase):
    def test_prefers_192_168_over_virtual_and_public_addresses(self):
        selected = config.choose_machine_ip([
            "172.20.0.1",
            "100.64.0.2",
            "192.168.1.88",
            "10.0.0.5",
        ])

        self.assertEqual("192.168.1.88", selected)

    def test_prefers_websocket_route_when_multiple_192_addresses_exist(self):
        with patch.object(
                config,
                "_local_ipv4_candidates",
                return_value=["192.168.56.1", "192.168.1.88"]) as resolver:
            selected = config.get_machine_ip("192.168.1.88")

        self.assertEqual("192.168.1.88", selected)
        resolver.assert_not_called()

    def test_parses_windows_ipconfig_adapter_addresses(self):
        output = """
Windows IP Configuration

Unknown adapter tunnel:
   IPv4 Address. . . . . . . . . . . : 10.64.0.2

Wireless LAN adapter WLAN:
   IPv4 Address. . . . . . . . . . . : 192.168.1.24
"""

        self.assertEqual(
            ["10.64.0.2", "192.168.1.24"],
            config._parse_ipconfig_ipv4(output),
        )

    def test_falls_back_to_other_rfc1918_networks(self):
        selected = config.choose_machine_ip([
            "8.8.8.8",
            "172.18.0.4",
            "10.10.0.9",
        ])

        self.assertEqual("10.10.0.9", selected)

    def test_ignores_loopback_link_local_and_invalid_addresses(self):
        selected = config.choose_machine_ip([
            "not-an-ip",
            "127.0.0.1",
            "169.254.10.20",
        ])

        self.assertEqual("127.0.0.1", selected)


if __name__ == "__main__":
    unittest.main()
