import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game_executor.executor.hardware.humanized import (
    HumanizationPolicy,
    HumanizedInputController,
)
from game_executor.executor.hardware.manual import ManualActionHardwareController


class _ConstantRandom:
    def randint(self, low, _high):
        return low

    def uniform(self, low, _high):
        return low


class _Device:
    def __init__(self):
        self.moves = []
        self.clicks = []
        self.drags = []
        self.keys = []
        self.combos = []
        self.move_result = True

    def mouse_move(self, x, y, **options):
        self.moves.append((x, y, options))
        return self.move_result

    def mouse_click(self, button="left"):
        self.clicks.append(button)
        return True

    def mouse_drag(self, x1, y1, x2, y2):
        self.drags.append((x1, y1, x2, y2))
        return True

    def key_press(self, key, duration_ms=100):
        self.keys.append((key, duration_ms))
        return True

    def key_combo(self, keys, duration_ms=100):
        self.combos.append((keys, duration_ms))
        return True


ZERO_DELAY_POLICY = HumanizationPolicy(
    before_action_seconds=(0, 0),
    pointer_settle_seconds=(0, 0),
    after_action_seconds=(0, 0),
    double_click_interval_seconds=(0, 0),
    key_gap_seconds=(0, 0),
)


class HumanizedInputControllerTest(unittest.TestCase):
    def test_repeated_click_stays_in_range_but_never_repeats_consecutively(self):
        device = _Device()
        controller = HumanizedInputController(
            device,
            policy=ZERO_DELAY_POLICY,
            random_source=_ConstantRandom(),
            sleep=lambda _seconds: None,
        )

        controller.click_at(100, 200)
        controller.click_at(100, 200)
        controller.click_at(100, 200)

        points = [(x, y) for x, y, _options in device.moves]
        self.assertEqual(3, len(points))
        self.assertNotEqual(points[0], points[1])
        self.assertNotEqual(points[1], points[2])
        self.assertTrue(all(97 <= x <= 103 and 197 <= y <= 203 for x, y in points))
        self.assertTrue(all(options == {
            "trajectory": "human", "jitter_x": 0, "jitter_y": 0
        } for _x, _y, options in device.moves))

    def test_click_is_clamped_to_screen_and_does_not_click_if_move_fails(self):
        device = _Device()
        controller = HumanizedInputController(
            device,
            policy=ZERO_DELAY_POLICY,
            random_source=_ConstantRandom(),
            sleep=lambda _seconds: None,
        )

        self.assertTrue(controller.click_at(0, 0, bounds=(0, 0, 799, 599)))
        x, y, _options = device.moves[-1]
        self.assertTrue(0 <= x <= 3)
        self.assertTrue(0 <= y <= 3)

        device.move_result = False
        self.assertFalse(controller.click_at(300, 200))
        self.assertEqual(1, len(device.clicks))

    def test_drag_varies_both_ends_within_separate_controlled_ranges(self):
        device = _Device()
        controller = HumanizedInputController(
            device,
            policy=ZERO_DELAY_POLICY,
            random_source=_ConstantRandom(),
            sleep=lambda _seconds: None,
        )

        self.assertTrue(controller.drag((100, 100), (300, 300)))

        x1, y1, x2, y2 = device.drags[0]
        self.assertTrue(98 <= x1 <= 102 and 98 <= y1 <= 102)
        self.assertTrue(294 <= x2 <= 306 and 294 <= y2 <= 306)

    def test_typing_uses_per_character_hold_and_gap_ranges(self):
        device = _Device()
        sleeps = []
        policy = HumanizationPolicy(
            before_action_seconds=(0, 0),
            pointer_settle_seconds=(0, 0),
            after_action_seconds=(0, 0),
            double_click_interval_seconds=(0, 0),
            key_hold_ms=(60, 90),
            key_gap_seconds=(0.04, 0.08),
        )
        controller = HumanizedInputController(
            device,
            policy=policy,
            random_source=_ConstantRandom(),
            sleep=sleeps.append,
        )

        self.assertTrue(controller.type_text("27"))

        self.assertEqual(["2", "7"], [key for key, _hold in device.keys])
        self.assertTrue(all(60 <= hold <= 90 for _key, hold in device.keys))
        self.assertTrue(all(0.04 <= delay <= 0.08 for delay in sleeps))

    def test_manual_mode_logs_a_whole_typing_plan_as_one_action(self):
        device = ManualActionHardwareController(action_wait_seconds=0)
        controller = HumanizedInputController(
            device,
            policy=ZERO_DELAY_POLICY,
            random_source=_ConstantRandom(),
            sleep=lambda _seconds: None,
        )

        with mock.patch("builtins.print"):
            self.assertTrue(controller.type_text("123"))

        self.assertEqual(1, device.planned_actions)

    def test_cancelled_action_never_reaches_device(self):
        device = _Device()
        controller = HumanizedInputController(
            device,
            policy=ZERO_DELAY_POLICY,
            sleep=lambda _seconds: None,
            cancelled=lambda: True,
        )

        self.assertFalse(controller.click_at(100, 200))
        self.assertFalse(controller.type_text("1"))
        self.assertEqual([], device.moves)
        self.assertEqual([], device.keys)

    def test_cancellation_during_pre_action_delay_stops_before_hardware_call(self):
        device = _Device()
        cancelled = [False]

        def cancel_during_sleep(_seconds):
            cancelled[0] = True

        controller = HumanizedInputController(
            device,
            policy=ZERO_DELAY_POLICY,
            sleep=cancel_during_sleep,
            cancelled=lambda: cancelled[0],
        )

        self.assertFalse(controller.click_at(100, 200))
        self.assertEqual([], device.moves)
        self.assertEqual([], device.clicks)


if __name__ == "__main__":
    unittest.main()
