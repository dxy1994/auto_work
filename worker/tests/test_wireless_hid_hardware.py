import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game_executor.executor.hardware.controller import HardwareController
from game_executor.executor.hardware.whid_sdk import DiscoveredDevice


class _FakeClient:
    def __init__(self, online=True):
        self.connected = False
        self.online = online
        self.calls = []

    def connect(self):
        self.connected = True
        self.calls.append(("connect",))
        return self

    def status(self):
        self.calls.append(("status",))
        return {
            "claimed": True,
            "ch9329_online": self.online,
            "wifi_rssi": -42,
            "uptime_seconds": 10,
        }

    def keyboard(self, modifier=0, keys=(), *, tap=True):
        self.calls.append(("keyboard", modifier, tuple(keys), tap))

    def mouse_relative(self, buttons=0, x=0, y=0, wheel=0):
        self.calls.append(("mouse_relative", buttons, x, y, wheel))

    def mouse_absolute(self, buttons=0, x=0, y=0, wheel=0):
        self.calls.append(("mouse_absolute", buttons, x, y, wheel))

    def release_all(self):
        self.calls.append(("release_all",))

    def close(self):
        self.calls.append(("close",))
        self.connected = False


class _ClientFactory:
    def __init__(self, client):
        self.client = client
        self.arguments = []

    def __call__(self, host, port):
        self.arguments.append((host, port))
        return self.client


class WirelessHidHardwareTest(unittest.TestCase):
    def make_controller(self, client=None):
        client = client or _FakeClient()
        sleeps = []
        feedback = []
        controller = HardwareController(
            "192.168.1.31",
            39667,
            client_factory=_ClientFactory(client),
            random_source=random.Random(7),
            sleep=sleeps.append,
            screen_bounds=(0, 0, 999, 999),
            cursor_provider=lambda: (0, 0),
            feedback_callback=feedback.append,
        )
        self.assertTrue(controller.connect())
        return controller, client, sleeps, feedback

    def test_mouse_move_uses_multi_point_trajectory_and_reports_completion(self):
        controller, client, sleeps, feedback = self.make_controller()

        self.assertTrue(controller.mouse_move(500, 250, jitter_x=0, jitter_y=0))

        reports = [call for call in client.calls if call[0] == "mouse_absolute"]
        self.assertGreater(len(reports), 10)
        self.assertEqual(("mouse_absolute", 0, 2050, 1025, 0), reports[-1])
        self.assertGreater(len(sleeps), len(reports))
        self.assertEqual("mouse_move", controller.last_feedback["action"])
        self.assertTrue(controller.last_feedback["success"])
        self.assertEqual(controller.last_feedback, feedback[-1].to_dict())

    def test_left_and_right_click_send_press_then_release(self):
        controller, client, _sleeps, _feedback = self.make_controller()

        self.assertTrue(controller.mouse_click("left"))
        self.assertTrue(controller.mouse_click("right"))

        reports = [call for call in client.calls if call[0] == "mouse_relative"]
        self.assertEqual(
            [
                ("mouse_relative", 1, 0, 0, 0),
                ("mouse_relative", 0, 0, 0, 0),
                ("mouse_relative", 2, 0, 0, 0),
                ("mouse_relative", 0, 0, 0, 0),
            ],
            reports,
        )

    def test_scroll_down_is_segmented_and_reports_after_all_notches(self):
        controller, client, sleeps, feedback = self.make_controller()
        feedback.clear()
        sleeps.clear()

        self.assertTrue(controller.mouse_scroll(-4))

        reports = [call for call in client.calls if call[0] == "mouse_relative"]
        self.assertEqual(
            [("mouse_relative", 0, 0, 0, -1)] * 4,
            reports,
        )
        self.assertGreaterEqual(len(sleeps), 5)
        self.assertEqual(1, len(feedback))
        self.assertEqual("mouse_scroll", feedback[0].action)
        self.assertTrue(feedback[0].success)

    def test_typing_plan_is_slow_randomized_and_feedback_is_after_full_text(self):
        controller, client, sleeps, feedback = self.make_controller()
        feedback.clear()
        sleeps.clear()
        plan = [
            {"key": "A", "hold_ms": 10, "gap_ms": 20},
            {"key": "2", "hold_ms": 90, "gap_ms": 140},
        ]

        self.assertTrue(controller.key_type_plan("A2", plan))

        keyboard = [call for call in client.calls if call[0] == "keyboard"]
        self.assertEqual(
            [
                ("keyboard", 2, (4,), False),
                ("keyboard", 0, (), False),
                ("keyboard", 0, (31,), False),
                ("keyboard", 0, (), False),
            ],
            keyboard,
        )
        self.assertGreaterEqual(sleeps[0], 0.075)
        self.assertGreaterEqual(sleeps[1], 0.080)
        self.assertGreaterEqual(sleeps[2], 0.075)
        self.assertGreaterEqual(sleeps[3], 0.080)
        self.assertEqual(1, len(feedback))
        self.assertEqual("key_type", feedback[0].action)
        self.assertTrue(feedback[0].success)

    def test_offline_ch9329_rejects_connection_with_failure_feedback(self):
        client = _FakeClient(online=False)
        factory = _ClientFactory(client)
        controller = HardwareController(
            "192.168.1.31",
            client_factory=factory,
            sleep=lambda _seconds: None,
        )

        self.assertFalse(controller.connect())
        self.assertFalse(controller.connected)
        self.assertEqual("connect", controller.last_feedback["action"])
        self.assertFalse(controller.last_feedback["success"])
        self.assertIn("CH9329 is offline", controller.last_feedback["error"])

    def test_bound_device_identity_is_verified_before_tcp_claim(self):
        client = _FakeClient()
        factory = _ClientFactory(client)
        controller = HardwareController(
            "192.168.1.31",
            39667,
            client_factory=factory,
            expected_device_id="AABBCCDDEEFF",
            discovery=lambda _host, _timeout: DiscoveredDevice(
                device_id="001122334455",
                name="wrong-device",
                ip="192.168.1.31",
                control_port=39667,
                claimed=False,
                ch9329=True,
            ),
            sleep=lambda _seconds: None,
        )

        self.assertFalse(controller.connect())
        self.assertEqual([], factory.arguments)
        self.assertIn("identity mismatch", controller.last_feedback["error"])

    def test_matching_bound_device_is_claimed(self):
        client = _FakeClient()
        factory = _ClientFactory(client)
        controller = HardwareController(
            "192.168.1.31",
            39667,
            client_factory=factory,
            expected_device_id="AABBCCDDEEFF",
            discovery=lambda _host, _timeout: DiscoveredDevice(
                device_id="AABBCCDDEEFF",
                name="assigned-device",
                ip="192.168.1.31",
                control_port=39667,
                claimed=False,
                ch9329=True,
            ),
            sleep=lambda _seconds: None,
        )

        self.assertTrue(controller.connect())
        self.assertEqual([("192.168.1.31", 39667)], factory.arguments)

    def test_health_check_contains_last_command_feedback(self):
        controller, _client, _sleeps, _feedback = self.make_controller()
        self.assertTrue(controller.key_press("F3", duration_ms=100))

        health = controller.health_check()

        self.assertTrue(health["connected"])
        self.assertTrue(health["ch9329_online"])
        self.assertEqual("key_press", health["last_command"]["action"])
        self.assertTrue(health["last_command"]["success"])

    def test_health_check_distinguishes_control_connection_from_ch9329_ready(self):
        controller, client, _sleeps, _feedback = self.make_controller()
        client.online = False

        health = controller.health_check()

        self.assertTrue(health["connected"])
        self.assertFalse(health["ready"])
        self.assertFalse(health["ch9329_online"])
        self.assertTrue(controller.connected)


if __name__ == "__main__":
    unittest.main()
