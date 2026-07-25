import json
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

    def test_action_log_contains_actual_coordinate_and_complete_input_text(self):
        device = _Device()
        controller = HumanizedInputController(
            device,
            policy=ZERO_DELAY_POLICY,
            random_source=_ConstantRandom(),
            sleep=lambda _seconds: None,
        )

        with mock.patch("builtins.print") as output:
            controller.click_at(100, 200)
            controller.type_text("250000")

        actions = []
        for call in output.call_args_list:
            line = call.args[0]
            if line.startswith("[GAME-ACTION] "):
                actions.append(json.loads(line.removeprefix("[GAME-ACTION] ")))

        self.assertEqual([97, 197], actions[0]["actual"])
        self.assertEqual("screen_absolute", actions[0]["coordinate_space"])
        self.assertEqual("250000", actions[1]["text"])
        self.assertEqual("planned", actions[1]["phase"])

    def test_manual_click_logs_client_and_screen_coordinate_conversion(self):
        device = ManualActionHardwareController(action_wait_seconds=0)
        controller = HumanizedInputController(
            device,
            policy=ZERO_DELAY_POLICY,
            random_source=_ConstantRandom(),
            sleep=lambda _seconds: None,
        )

        with mock.patch("builtins.print") as output:
            controller.click_at(
                984,
                797,
                radius_x=0,
                radius_y=0,
                coordinate_origin=(190, 213),
            )

        logged = {}
        for call in output.call_args_list:
            line = call.args[0]
            if line.startswith("[GAME-ACTION] "):
                logged["game"] = json.loads(
                    line.removeprefix("[GAME-ACTION] ")
                )
            elif line.startswith("[MANUAL-ACTION] "):
                logged["manual"] = json.loads(
                    line.removeprefix("[MANUAL-ACTION] ")
                )

        for action in logged.values():
            self.assertEqual([190, 213], action["client_origin"])
            self.assertEqual([794, 584], action["client_target"])
            self.assertEqual([794, 584], action["client_actual"])
            self.assertEqual([984, 797], action["screen_target"])
            self.assertEqual([984, 797], action["screen_actual"])
            self.assertEqual(
                [794, 584, 794, 584],
                action["client_action_bounds"],
            )
            self.assertEqual(
                [984, 797, 984, 797],
                action["screen_action_bounds"],
            )
        self.assertIn("游戏客户区坐标 (794,584)", logged["manual"]["instruction"])
        self.assertIn("客户区原点 (190,213)", logged["manual"]["instruction"])
        self.assertIn(
            "允许操作范围 X[794,794] Y[584,584]",
            logged["manual"]["instruction"],
        )

    def test_click_logs_effective_action_region_after_bounds_intersection(self):
        device = _Device()
        controller = HumanizedInputController(
            device,
            policy=ZERO_DELAY_POLICY,
            random_source=_ConstantRandom(),
            sleep=lambda _seconds: None,
        )

        with mock.patch("builtins.print") as output:
            controller.click_at(
                110,
                220,
                radius_x=3,
                radius_y=2,
                bounds=(109, 219, 112, 225),
                coordinate_origin=(10, 20),
            )

        line = next(
            call.args[0]
            for call in output.call_args_list
            if call.args[0].startswith("[GAME-ACTION] ")
        )
        action = json.loads(line.removeprefix("[GAME-ACTION] "))
        self.assertEqual([109, 219, 112, 222], action["screen_action_bounds"])
        self.assertEqual([99, 199, 102, 202], action["client_action_bounds"])

    def test_click_visualizer_path_is_included_without_changing_action(self):
        device = _Device()
        controller = HumanizedInputController(
            device,
            policy=ZERO_DELAY_POLICY,
            random_source=_ConstantRandom(),
            sleep=lambda _seconds: None,
        )
        visualized = []
        controller.set_action_visualizer(
            lambda action: visualized.append(action) or r"C:\temp\action.png"
        )

        with mock.patch("builtins.print") as output:
            self.assertTrue(controller.click_at(100, 200))

        line = next(
            call.args[0]
            for call in output.call_args_list
            if call.args[0].startswith("[GAME-ACTION] ")
        )
        action = json.loads(line.removeprefix("[GAME-ACTION] "))
        self.assertEqual(r"C:\temp\action.png", action["visual_debug_image"])
        self.assertEqual("mouse_click", visualized[0]["action"])
        self.assertEqual(1, len(device.clicks))

    def test_visualizer_receives_drag_and_keyboard_actions(self):
        device = _Device()
        controller = HumanizedInputController(
            device,
            policy=ZERO_DELAY_POLICY,
            random_source=_ConstantRandom(),
            sleep=lambda _seconds: None,
        )
        visualized = []
        controller.set_action_visualizer(
            lambda action: visualized.append(action) or (
                rf"C:\temp\{action['action']}.png"
            )
        )

        with mock.patch("builtins.print") as output:
            self.assertTrue(controller.drag(
                (100, 100),
                (300, 300),
                coordinate_origin=(10, 20),
            ))
            self.assertTrue(controller.type_text("27"))
            self.assertTrue(controller.press_key("enter"))
            self.assertTrue(controller.press_combo(["ctrl", "a"]))

        self.assertEqual(
            ["mouse_drag", "key_type", "key_press", "key_combo"],
            [action["action"] for action in visualized],
        )
        logged_actions = [
            json.loads(call.args[0].removeprefix("[GAME-ACTION] "))
            for call in output.call_args_list
            if call.args[0].startswith("[GAME-ACTION] ")
        ]
        self.assertTrue(all("visual_debug_image" in action for action in logged_actions))
        self.assertEqual(1, len(device.drags))
        self.assertEqual(["2", "7", "enter"], [key for key, _hold in device.keys])
        self.assertEqual([(["ctrl", "a"], 55)], device.combos)

    def test_drag_logs_effective_start_and_end_regions(self):
        device = _Device()
        controller = HumanizedInputController(
            device,
            policy=ZERO_DELAY_POLICY,
            random_source=_ConstantRandom(),
            sleep=lambda _seconds: None,
        )

        with mock.patch("builtins.print") as output:
            self.assertTrue(controller.drag(
                (100, 100),
                (300, 300),
                bounds=(0, 0, 799, 599),
                coordinate_origin=(10, 20),
            ))

        line = next(
            call.args[0]
            for call in output.call_args_list
            if call.args[0].startswith("[GAME-ACTION] ")
        )
        action = json.loads(line.removeprefix("[GAME-ACTION] "))
        self.assertEqual([98, 98, 102, 102], action["screen_start_action_bounds"])
        self.assertEqual([294, 294, 306, 306], action["screen_end_action_bounds"])
        self.assertEqual([88, 78, 92, 82], action["client_start_action_bounds"])
        self.assertEqual([284, 274, 296, 286], action["client_end_action_bounds"])

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
