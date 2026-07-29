import os
import random
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game_executor.hid_browser_debug import run_debug_sequence


class _InputRecorder:
    def __init__(self):
        self.actions = []

    def press_combo(self, keys):
        self.actions.append(("combo", tuple(keys)))
        return True

    def type_text(self, text):
        self.actions.append(("type", str(text)))
        return True

    def press_key(self, key):
        self.actions.append(("key", str(key)))
        return True

    def click_at(self, x, y, **options):
        self.actions.append(("click", x, y, options))
        return True

    def move_to(self, x, y, **options):
        self.actions.append(("move", x, y, options))
        return True

    def scroll(self, steps):
        self.actions.append(("scroll", steps))
        return True


class _HardwareFeedback:
    @property
    def last_feedback(self):
        return {
            "action": "fake",
            "success": True,
        }


class HidBrowserDebugTest(unittest.TestCase):
    def test_sequence_is_synchronous_and_ends_with_downward_scroll(self):
        input_controller = _InputRecorder()
        sleeps = []
        output = []

        result = run_debug_sequence(
            input_controller,
            _HardwareFeedback(),
            random_source=random.Random(23),
            sleep=sleeps.append,
            screen_bounds=(0, 0, 999, 799),
            emit=output.append,
        )

        action_names = [action[0] for action in input_controller.actions]
        self.assertEqual(
            [
                "combo",
                "type",
                "key",
                "click",
                "type",
                "key",
                "move",
                "scroll",
            ],
            action_names,
        )
        self.assertEqual(("win", "r"), input_controller.actions[0][1])
        self.assertEqual("google.com", input_controller.actions[1][1])
        self.assertEqual("ENTER", input_controller.actions[2][1])
        self.assertRegex(result["query"], re.compile(r"^[a-z0-9]{8,14}$"))
        self.assertEqual(result["query"], input_controller.actions[4][1])
        self.assertEqual("ENTER", input_controller.actions[5][1])
        self.assertEqual(result["random_target"], input_controller.actions[6][1:3])
        self.assertEqual(result["scroll_steps"], input_controller.actions[7][1])
        self.assertTrue(-12 <= result["scroll_steps"] <= -6)
        self.assertEqual(4, len(sleeps))
        self.assertEqual(8, len(output))
        self.assertTrue(all('"status":"completed"' in line for line in output))


if __name__ == "__main__":
    unittest.main()
