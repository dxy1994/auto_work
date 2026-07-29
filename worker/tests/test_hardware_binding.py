import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game_executor.hardware_binding import WirelessHidBinding


class HardwareBindingTest(unittest.TestCase):
    def test_valid_controller_payload_is_normalized(self):
        binding = WirelessHidBinding.from_payload({
            "record_id": 2,
            "device_id": "aabbccddeeff",
            "name": "二号键鼠",
            "ip": "192.168.1.32",
            "control_port": 39667,
        })

        self.assertEqual("AABBCCDDEEFF", binding.device_id)
        self.assertEqual("192.168.1.32", binding.host)
        self.assertEqual(39667, binding.port)

    def test_invalid_or_incomplete_payload_is_rejected(self):
        invalid_rows = [
            {},
            {
                "record_id": 2,
                "device_id": "NOT-A-DEVICE",
                "ip": "192.168.1.32",
                "control_port": 39667,
            },
            {
                "record_id": 2,
                "device_id": "AABBCCDDEEFF",
                "ip": "not-an-ip",
                "control_port": 39667,
            },
        ]

        for payload in invalid_rows:
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    WirelessHidBinding.from_payload(payload)


if __name__ == "__main__":
    unittest.main()
