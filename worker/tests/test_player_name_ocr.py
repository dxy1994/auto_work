import os
import sys
import unittest

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game_executor.executor.lineage_classic.player_name_ocr import (
    estimated_character_width,
    recognize_expected_player_name,
    segment_expected_name,
    split_expected_name,
)


class PlayerNameOcrTest(unittest.TestCase):
    def test_mixed_name_is_split_into_continuous_script_runs(self):
        runs = split_expected_name("TT석사TT")

        self.assertEqual(
            [
                ("english", "T"),
                ("english", "T"),
                ("korean", "석사"),
                ("english", "T"),
                ("english", "T"),
            ],
            [(run.kind, run.text) for run in runs],
        )
        self.assertGreater(
            estimated_character_width("석"),
            estimated_character_width("T"),
        )

    def test_segment_boundaries_follow_configured_character_widths(self):
        image = np.zeros((22, 100, 3), dtype=np.uint8)
        # 起点为 X=5；三个文字段之间各留空白列，模拟浅色游戏字体。
        cv2.rectangle(image, (5, 4), (19, 18), (220, 220, 220), 1)
        cv2.rectangle(image, (22, 3), (44, 19), (220, 220, 220), 1)
        cv2.rectangle(image, (47, 4), (61, 18), (220, 220, 220), 1)

        segments = segment_expected_name(image, "TT석사TT")

        self.assertEqual(5, len(segments))
        self.assertLessEqual(segments[0].left, 5)
        self.assertLess(segments[0].right, segments[2].left)
        self.assertEqual(55, segments[-1].right)

    def test_two_column_lowercase_r_is_not_skipped_as_border_noise(self):
        image = np.zeros((22, 80, 3), dtype=np.uint8)
        # 左侧边框噪声只有两个亮点；真正的 r 也是两列，但纵向亮点更多。
        image[5, 4] = (220, 220, 220)
        image[6, 5] = (220, 220, 220)
        cv2.rectangle(image, (12, 5), (13, 9), (220, 220, 220), 1)
        cv2.rectangle(image, (17, 4), (21, 18), (220, 220, 220), 1)

        segments = segment_expected_name(image, "ru")

        self.assertEqual(
            [("r", 12, 17), ("u", 17, 23)],
            [
                (segment.expected, segment.left, segment.right)
                for segment in segments
            ],
        )

    def test_mixed_vwxyz_korean_name_uses_proportional_widths(self):
        image = np.zeros((22, 120, 3), dtype=np.uint8)
        cv2.rectangle(image, (5, 4), (78, 18), (220, 220, 220), 1)

        segments = segment_expected_name(image, "VWXYZ사라YOU")

        self.assertEqual(
            [
                ("V", 5, 11),
                ("W", 11, 17),
                ("X", 17, 23),
                ("Y", 23, 29),
                ("Z", 29, 35),
                ("사라", 35, 61),
                ("Y", 61, 67),
                ("O", 67, 73),
                ("U", 73, 79),
            ],
            [
                (segment.expected, segment.left, segment.right)
                for segment in segments
            ],
        )

    def test_calibrated_uppercase_name_uses_exact_configured_boundaries(self):
        image = np.zeros((22, 120, 3), dtype=np.uint8)
        # 两个孤立亮点模拟弹窗边框噪声，姓名从 X=12 开始。
        image[5, 5] = (220, 220, 220)
        image[5, 6] = (220, 220, 220)
        for left, right in (
            (12, 17), (18, 23), (24, 29), (30, 36),
            (37, 42), (43, 48), (49, 54), (55, 62),
            (63, 67), (68, 73), (74, 79), (80, 85),
        ):
            cv2.rectangle(
                image,
                (left, 4),
                (right - 1, 18),
                (220, 220, 220),
                1,
            )

        segments = segment_expected_name(image, "ABCDEFGHIZKL")

        self.assertEqual(
            [
                (12, 18), (18, 24), (24, 30), (30, 37),
                (37, 43), (43, 49), (49, 55), (55, 63),
                (63, 68), (68, 74), (74, 80), (80, 86),
            ],
            [(segment.left, segment.right) for segment in segments],
        )

    def test_calibrated_lowercase_name_uses_exact_configured_boundaries(self):
        image = np.zeros((22, 120, 3), dtype=np.uint8)
        cv2.rectangle(image, (11, 4), (84, 18), (220, 220, 220), 1)

        segments = segment_expected_name(image, "abcdfjeghikl")

        self.assertEqual(
            [
                ("a", 11, 17),
                ("b", 17, 23),
                ("c", 23, 29),
                ("d", 29, 35),
                ("f", 35, 41),
                ("j", 41, 47),
                ("e", 47, 53),
                ("g", 53, 60),
                ("h", 60, 68),
                ("i", 68, 73),
                ("k", 73, 80),
                ("l", 80, 85),
            ],
            [
                (segment.expected, segment.left, segment.right)
                for segment in segments
            ],
        )

    def test_calibrated_m_to_x_name_uses_exact_units_and_ocr_crops(self):
        image = np.zeros((22, 140, 3), dtype=np.uint8)
        cv2.rectangle(image, (11, 4), (84, 18), (220, 220, 220), 1)

        segments = segment_expected_name(image, "mnopqlstyvwx")

        self.assertEqual(
            [
                ("m", 11, 17, 10, 17),
                ("n", 17, 23, 16, 22),
                ("o", 23, 29, 21, 28),
                ("p", 29, 35, 28, 35),
                ("q", 35, 42, 34, 42),
                ("l", 42, 47, 41, 46),
                ("s", 47, 53, 46, 53),
                ("t", 53, 61, 54, 60),
                ("y", 61, 67, 60, 67),
                ("v", 67, 73, 66, 73),
                ("w", 73, 79, 72, 79),
                ("x", 79, 85, 78, 85),
            ],
            [
                (
                    segment.expected,
                    segment.left,
                    segment.right,
                    segment.crop_left,
                    segment.crop_right,
                )
                for segment in segments
            ],
        )

    def test_mixed_korean_lokl_name_uses_calibrated_pair_spacing_and_crops(self):
        image = np.zeros((22, 140, 3), dtype=np.uint8)
        image[5, 4] = (220, 220, 220)
        image[6, 5] = (220, 220, 220)
        cv2.rectangle(image, (12, 4), (83, 18), (220, 220, 220), 1)

        segments = segment_expected_name(image, "킹차노스lokL")

        self.assertEqual(
            [
                ("킹차노스", 12, 64, 12, 64),
                ("l", 64, 68, 63, 67),
                ("o", 68, 74, 66, 73),
                ("k", 74, 79, 73, 79),
                ("L", 79, 85, 78, 85),
            ],
            [
                (
                    segment.expected,
                    segment.left,
                    segment.right,
                    segment.crop_left,
                    segment.crop_right,
                )
                for segment in segments
            ],
        )

    def test_mixed_name_applies_calibrated_character_pair_spacing(self):
        image = np.zeros((22, 140, 3), dtype=np.uint8)
        image[5, 4] = (220, 220, 220)
        image[6, 5] = (220, 220, 220)
        cv2.rectangle(image, (12, 4), (78, 18), (220, 220, 220), 1)

        segments = segment_expected_name(image, "ruyz호랑HMn")

        self.assertEqual(
            [
                ("r", 12, 17),
                ("u", 17, 23),
                ("y", 23, 29),
                ("z", 29, 35),
                ("호랑", 35, 61),
                ("H", 61, 67),
                ("M", 67, 73),
                ("n", 73, 79),
            ],
            [
                (segment.expected, segment.left, segment.right)
                for segment in segments
            ],
        )

    def test_unconfigured_korean_syllables_default_to_thirteen_pixels(self):
        image = np.zeros((22, 80, 3), dtype=np.uint8)
        cv2.rectangle(image, (5, 4), (43, 18), (220, 220, 220), 1)

        segments = segment_expected_name(image, "한글명")

        self.assertEqual(
            [("한글명", 5, 44)],
            [
                (segment.expected, segment.left, segment.right)
                for segment in segments
            ],
        )

    def test_english_and_korean_runs_use_separate_recognizers_then_reassemble(self):
        image = np.zeros((22, 100, 3), dtype=np.uint8)
        cv2.rectangle(image, (5, 4), (19, 18), (220, 220, 220), 1)
        cv2.rectangle(image, (22, 3), (44, 19), (220, 220, 220), 1)
        cv2.rectangle(image, (47, 4), (61, 18), (220, 220, 220), 1)
        languages = []

        def recognize(_image, language):
            languages.append(language)
            return ("T", 98.0) if language == "english" else ("석사", 96.0)

        result = recognize_expected_player_name(
            image,
            "TT석사TT",
            recognizer=recognize,
        )

        self.assertEqual("TT석사TT", result.text)
        self.assertEqual(96.0, result.confidence)
        self.assertTrue(result.verified)
        self.assertEqual("segmented_exact", result.strategy)
        # 高置信精确命中后立即停止该段的其他预处理版本。
        self.assertEqual(
            [
                "english",
                "english",
                "korean",
                "english",
                "english",
            ],
            languages[:5],
        )

    def test_korean_run_discards_english_ocr_noise_before_matching(self):
        image = np.zeros((22, 80, 3), dtype=np.uint8)
        cv2.rectangle(image, (5, 4), (30, 18), (220, 220, 220), 1)

        def recognize(_image, language):
            self.assertEqual("korean", language)
            return "TT석사YesNo", 96.0

        result = recognize_expected_player_name(
            image,
            "석사",
            recognizer=recognize,
        )

        self.assertEqual("석사", result.text)
        self.assertEqual("석사", result.visual_observed)
        self.assertTrue(result.verified)
        self.assertEqual("segmented_exact", result.strategy)

    def test_unsupported_name_characters_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "不支持"):
            split_expected_name("TT-석사")

    def test_expected_o_accepts_high_confidence_zero_visual_result(self):
        image = np.zeros((22, 30, 3), dtype=np.uint8)
        cv2.rectangle(image, (5, 4), (9, 18), (220, 220, 220), 1)

        def recognize(_image, language):
            self.assertEqual("english", language)
            return "0", 98.8

        result = recognize_expected_player_name(
            image,
            "O",
            recognizer=recognize,
        )

        self.assertEqual("O", result.text)
        self.assertEqual("0", result.visual_observed)
        self.assertTrue(result.verified)
        self.assertTrue(result.runs[0].high_risk_equivalent)
        self.assertEqual("segmented_high_risk_equivalent", result.strategy)

    def test_expected_lowercase_l_accepts_uppercase_i_visual_result(self):
        image = np.zeros((22, 30, 3), dtype=np.uint8)
        cv2.rectangle(image, (5, 4), (8, 18), (220, 220, 220), 1)

        def recognize(_image, language):
            self.assertEqual("english", language)
            return "I", 92.4

        result = recognize_expected_player_name(
            image,
            "l",
            recognizer=recognize,
        )

        self.assertEqual("l", result.text)
        self.assertEqual("I", result.visual_observed)
        self.assertTrue(result.runs[0].high_risk_equivalent)
        self.assertTrue(result.verified)
        self.assertEqual("segmented_high_risk_equivalent", result.strategy)

    def test_expected_uppercase_i_accepts_lowercase_l_visual_result(self):
        image = np.zeros((22, 30, 3), dtype=np.uint8)
        cv2.rectangle(image, (5, 4), (9, 18), (220, 220, 220), 1)

        def recognize(_image, language):
            self.assertEqual("english", language)
            return "l", 91.8

        result = recognize_expected_player_name(
            image,
            "I",
            recognizer=recognize,
        )

        self.assertEqual("I", result.text)
        self.assertEqual("l", result.visual_observed)
        self.assertTrue(result.runs[0].high_risk_equivalent)
        self.assertTrue(result.verified)
        self.assertEqual("segmented_high_risk_equivalent", result.strategy)

    def test_expected_lowercase_g_accepts_nine_visual_result(self):
        image = np.zeros((22, 30, 3), dtype=np.uint8)
        cv2.rectangle(image, (5, 4), (10, 18), (220, 220, 220), 1)

        def recognize(_image, language):
            self.assertEqual("english", language)
            return "9", 74.6

        result = recognize_expected_player_name(
            image,
            "g",
            recognizer=recognize,
        )

        self.assertEqual("g", result.text)
        self.assertEqual("9", result.visual_observed)
        self.assertTrue(result.runs[0].high_risk_equivalent)
        self.assertTrue(result.verified)
        self.assertEqual("segmented_high_risk_equivalent", result.strategy)

    def test_invalid_punctuation_visuals_are_scoped_to_expected_r_and_z(self):
        image = np.zeros((22, 30, 3), dtype=np.uint8)
        cv2.rectangle(image, (5, 4), (15, 18), (220, 220, 220), 1)
        answers = iter(
            [(",", 95.2)] * 4
            + [(":", 99.7)] * 4
        )

        def recognize(_image, language):
            self.assertEqual("english", language)
            return next(answers)

        result = recognize_expected_player_name(
            image,
            "rz",
            recognizer=recognize,
        )

        self.assertEqual("rz", result.text)
        self.assertEqual(",:", result.visual_observed)
        self.assertTrue(result.verified)
        self.assertTrue(all(run.high_risk_equivalent for run in result.runs))
        self.assertEqual("segmented_high_risk_equivalent", result.strategy)

    def test_known_letter_punctuation_visuals_are_high_risk_equivalents(self):
        image = np.zeros((22, 80, 3), dtype=np.uint8)
        cv2.rectangle(image, (5, 4), (45, 18), (220, 220, 220), 1)
        answers = iter(
            [("!", 95.1)] * 4
            + [("(", 94.2)] * 4
            + [(";", 93.3)] * 4
            + [("$", 92.4)] * 4
            + [("+", 91.5)] * 4
            + [("*", 90.6)] * 4
            + [("[", 89.7)] * 4
        )

        def recognize(_image, language):
            self.assertEqual("english", language)
            return next(answers)

        result = recognize_expected_player_name(
            image,
            "iCjsTxL",
            recognizer=recognize,
        )

        self.assertEqual("iCjsTxL", result.text)
        self.assertEqual("!(;$+*[", result.visual_observed)
        self.assertTrue(result.verified)
        self.assertTrue(all(run.high_risk_equivalent for run in result.runs))
        self.assertEqual("segmented_high_risk_equivalent", result.strategy)

    def test_punctuation_visual_does_not_match_unrelated_expected_letter(self):
        image = np.zeros((22, 30, 3), dtype=np.uint8)
        cv2.rectangle(image, (5, 4), (10, 18), (220, 220, 220), 1)

        def recognize(_image, _language):
            return "!", 99.0

        result = recognize_expected_player_name(
            image,
            "A",
            recognizer=recognize,
        )

        self.assertEqual("!", result.text)
        self.assertFalse(result.verified)
        self.assertFalse(result.runs[0].high_risk_equivalent)

    def test_exact_match_is_preferred_over_higher_confidence_risky_match(self):
        image = np.zeros((22, 30, 3), dtype=np.uint8)
        cv2.rectangle(image, (5, 4), (8, 18), (220, 220, 220), 1)
        answers = iter((("I", 96.0), ("l", 71.0)))

        def recognize(_image, language):
            self.assertEqual("english", language)
            return next(answers)

        result = recognize_expected_player_name(
            image,
            "l",
            recognizer=recognize,
        )

        self.assertEqual("l", result.visual_observed)
        self.assertFalse(result.runs[0].high_risk_equivalent)
        self.assertTrue(result.verified)
        self.assertEqual("segmented_exact", result.strategy)

    def test_known_tt_name_accepts_strict_korean_visual_equivalent(self):
        image = np.zeros((22, 120, 3), dtype=np.uint8)
        cv2.rectangle(image, (5, 4), (16, 18), (220, 220, 220), 1)
        cv2.rectangle(image, (19, 3), (52, 19), (220, 220, 220), 1)
        cv2.rectangle(image, (55, 4), (66, 18), (220, 220, 220), 1)

        def recognize(prepared, language):
            if language == "korean" and prepared.shape[1] > 250:
                return "w석사ㅠ이(가]", 86.7
            return "", 20.0

        result = recognize_expected_player_name(
            image,
            "TT석사TT",
            recognizer=recognize,
        )

        self.assertEqual("TT석사TT", result.text)
        self.assertEqual("w석사ㅠ이(가]", result.visual_observed)
        self.assertAlmostEqual(86.7, result.confidence)
        self.assertTrue(result.verified)
        self.assertEqual("korean_visual_constrained", result.strategy)


if __name__ == "__main__":
    unittest.main()
