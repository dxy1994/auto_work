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
from game_executor.executor.lineage_classic.font_metrics import (
    korean_ocr_text_matches,
)


class PlayerNameOcrTest(unittest.TestCase):
    def test_all_english_letters_use_ten_pixel_advance_at_1280x960(self):
        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"

        self.assertEqual(
            {10},
            {estimated_character_width(char) for char in letters},
        )

    def test_real_trade_panel_border_noise_is_not_used_as_name_start(self):
        image = np.zeros((35, 160, 3), dtype=np.uint8)
        image[2:5, 4] = (220, 220, 220)
        image[2:4, 6:9] = (220, 220, 220)
        cv2.rectangle(image, (17, 13), (24, 25), (220, 220, 220), 1)

        segments = segment_expected_name(image, "ABC")

        self.assertEqual(
            [("A", 17, 27), ("B", 27, 37), ("C", 37, 47)],
            [
                (segment.expected, segment.left, segment.right)
                for segment in segments
            ],
        )

    def test_korean_to_english_transition_uses_trade_panel_cell_origin(self):
        image = np.zeros((35, 140, 3), dtype=np.uint8)
        image[2:17, 4] = (220, 220, 220)
        image[2:4, 6:9] = (220, 220, 220)
        cv2.rectangle(image, (19, 8), (73, 25), (220, 220, 220), 1)

        segments = segment_expected_name(image, "꼬망임DL")

        self.assertEqual(
            [
                ("꼬망임", 17, 77, 19, 77),
                ("D", 77, 87, 75, 87),
                ("L", 87, 97, 85, 97),
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
        self.assertEqual(85, segments[-1].right)

    def test_two_column_lowercase_r_is_not_skipped_as_border_noise(self):
        image = np.zeros((22, 80, 3), dtype=np.uint8)
        # 左侧边框噪声只有两个亮点；真正的 r 也是两列，但纵向亮点更多。
        image[5, 4] = (220, 220, 220)
        image[6, 5] = (220, 220, 220)
        cv2.rectangle(image, (12, 5), (13, 9), (220, 220, 220), 1)
        cv2.rectangle(image, (17, 4), (21, 18), (220, 220, 220), 1)

        segments = segment_expected_name(image, "ru")

        self.assertEqual(
            [("r", 10, 20), ("u", 20, 30)],
            [
                (segment.expected, segment.left, segment.right)
                for segment in segments
            ],
        )

    def test_repeated_uppercase_t_does_not_overlap_previous_glyph(self):
        image = np.zeros((22, 60, 3), dtype=np.uint8)
        cv2.rectangle(image, (5, 4), (24, 18), (220, 220, 220), 1)

        segments = segment_expected_name(image, "TT")

        self.assertEqual(
            [
                ("T", 5, 15, 3, 17),
                ("T", 15, 25, 15, 27),
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

    def test_mixed_vwxyz_korean_name_uses_proportional_widths(self):
        image = np.zeros((22, 160, 3), dtype=np.uint8)
        cv2.rectangle(image, (5, 4), (78, 18), (220, 220, 220), 1)

        segments = segment_expected_name(image, "VWXYZ사라YOU")

        self.assertEqual(
            [
                ("V", 5, 15),
                ("W", 15, 25),
                ("X", 25, 35),
                ("Y", 35, 45),
                ("Z", 45, 55),
                ("사라", 55, 95),
                ("Y", 95, 105),
                ("O", 105, 115),
                ("U", 115, 125),
            ],
            [
                (segment.expected, segment.left, segment.right)
                for segment in segments
            ],
        )

    def test_calibrated_uppercase_name_uses_exact_configured_boundaries(self):
        image = np.zeros((22, 160, 3), dtype=np.uint8)
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
                (12, 22), (22, 32), (32, 42), (42, 52),
                (52, 62), (62, 72), (72, 82), (82, 92),
                (92, 102), (102, 112), (112, 122), (122, 132),
            ],
            [(segment.left, segment.right) for segment in segments],
        )

    def test_calibrated_lowercase_name_uses_exact_configured_boundaries(self):
        image = np.zeros((22, 160, 3), dtype=np.uint8)
        cv2.rectangle(image, (11, 4), (84, 18), (220, 220, 220), 1)

        segments = segment_expected_name(image, "abcdfjeghikl")

        self.assertEqual(
            [
                ("a", 11, 21),
                ("b", 21, 31),
                ("c", 31, 41),
                ("d", 41, 51),
                ("f", 51, 61),
                ("j", 61, 71),
                ("e", 71, 81),
                ("g", 81, 91),
                ("h", 91, 101),
                ("i", 101, 111),
                ("k", 111, 121),
                ("l", 121, 131),
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
                ("m", 11, 21, 9, 21),
                ("n", 21, 31, 19, 29),
                ("o", 31, 41, 28, 39),
                ("p", 41, 51, 39, 51),
                ("q", 51, 61, 49, 61),
                ("l", 61, 71, 59, 69),
                ("s", 71, 81, 69, 81),
                ("t", 81, 91, 83, 89),
                ("y", 91, 101, 89, 101),
                ("v", 101, 111, 99, 111),
                ("w", 111, 121, 109, 121),
                ("x", 121, 131, 119, 131),
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

    def test_mixed_korean_lokl_name_uses_fixed_english_spacing_and_crops(self):
        image = np.zeros((22, 140, 3), dtype=np.uint8)
        image[5, 4] = (220, 220, 220)
        image[6, 5] = (220, 220, 220)
        cv2.rectangle(image, (12, 4), (83, 18), (220, 220, 220), 1)

        segments = segment_expected_name(image, "킹차노스lokL")

        self.assertEqual(
            [
                ("킹차노스", 12, 92, 12, 92),
                ("l", 92, 102, 90, 100),
                ("o", 102, 112, 99, 110),
                ("k", 112, 122, 110, 122),
                ("L", 122, 132, 120, 132),
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

    def test_mixed_name_keeps_fixed_english_spacing_across_script_runs(self):
        image = np.zeros((22, 140, 3), dtype=np.uint8)
        image[5, 4] = (220, 220, 220)
        image[6, 5] = (220, 220, 220)
        cv2.rectangle(image, (12, 4), (78, 18), (220, 220, 220), 1)

        segments = segment_expected_name(image, "ruyz호랑HMn")

        self.assertEqual(
            [
                ("r", 10, 20),
                ("u", 20, 30),
                ("y", 30, 40),
                ("z", 40, 50),
                ("호랑", 50, 90),
                ("H", 90, 100),
                ("M", 100, 110),
                ("n", 110, 120),
            ],
            [
                (segment.expected, segment.left, segment.right)
                for segment in segments
            ],
        )

    def test_all_korean_syllables_use_twenty_pixel_advance_at_1280x960(self):
        image = np.zeros((22, 80, 3), dtype=np.uint8)
        cv2.rectangle(image, (5, 4), (43, 18), (220, 220, 220), 1)

        segments = segment_expected_name(image, "한글명")

        self.assertEqual(
            [("한글명", 5, 65)],
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

    def test_korean_dot_font_equivalents_are_expected_position_scoped(self):
        image = np.zeros((22, 140, 3), dtype=np.uint8)
        cv2.rectangle(image, (5, 4), (104, 18), (220, 220, 220), 1)

        def recognize(_image, language):
            self.assertEqual("korean", language)
            return "이풍리방니", 95.6

        result = recognize_expected_player_name(
            image,
            "이뚱리빵니",
            recognizer=recognize,
        )
        unrelated = recognize_expected_player_name(
            image,
            "이뚱리숙니",
            recognizer=recognize,
        )

        self.assertEqual("이뚱리빵니", result.text)
        self.assertEqual("이풍리방니", result.visual_observed)
        self.assertTrue(result.verified)
        self.assertTrue(result.runs[0].high_risk_equivalent)
        self.assertEqual("segmented_high_risk_equivalent", result.strategy)
        self.assertFalse(unrelated.verified)

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

    def test_1280_pixel_font_visual_equivalents_are_expected_position_scoped(self):
        image = np.zeros((35, 100, 3), dtype=np.uint8)
        cv2.rectangle(image, (5, 8), (64, 25), (220, 220, 220), 1)
        answers = iter(
            [("D", 91.0)] * 4
            + [("b", 92.0)] * 4
            + [("3", 93.0)] * 4
            + [("b", 94.0)] * 4
            + [("u", 95.0)] * 4
            + [("2", 96.0)] * 4
        )

        def recognize(_image, language):
            self.assertEqual("english", language)
            return next(answers)

        result = recognize_expected_player_name(
            image,
            "begoVZ",
            recognizer=recognize,
        )

        self.assertEqual("begoVZ", result.text)
        self.assertEqual("Db3bu2", result.visual_observed)
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

    def test_configured_korean_visual_groups_are_bidirectional(self):
        groups = (
            ("훅", "혹"),
            ("당", "탕", "댱", "턍"),
            ("옥", "욱", "종", "중"),
            ("쭉", "쪽"),
            ("횽", "흉"),
        )
        for group in groups:
            for expected in group:
                for observed in group:
                    with self.subTest(expected=expected, observed=observed):
                        self.assertTrue(korean_ocr_text_matches(
                            expected,
                            observed,
                        ))

    def test_korean_visual_groups_are_expected_position_scoped(self):
        self.assertTrue(korean_ocr_text_matches(
            "훅당옥쭉횽",
            "혹턍중쪽흉",
        ))
        self.assertFalse(korean_ocr_text_matches(
            "보라훅설탕",
            "보라핫설탕",
        ))
        self.assertFalse(korean_ocr_text_matches(
            "당옥",
            "욱탕",
        ))

    def test_real_buyer_name_accepts_constrained_korean_vowel_confusion(self):
        image = np.zeros((35, 200, 3), dtype=np.uint8)
        cv2.rectangle(image, (5, 8), (128, 25), (220, 220, 220), 1)

        def recognize(_prepared, language):
            self.assertEqual("korean", language)
            return "보라혹설탕이", 89.93

        result = recognize_expected_player_name(
            image,
            "보라훅설탕",
            recognizer=recognize,
        )

        self.assertEqual("보라훅설탕", result.text)
        self.assertEqual("보라혹설탕이", result.visual_observed)
        self.assertAlmostEqual(89.93, result.confidence)
        self.assertTrue(result.verified)
        self.assertEqual("korean_visual_constrained", result.strategy)

    def test_all_configured_korean_groups_work_in_constrained_line_ocr(self):
        image = np.zeros((35, 160, 3), dtype=np.uint8)
        cv2.rectangle(image, (5, 8), (88, 25), (220, 220, 220), 1)

        def recognize(_prepared, language):
            self.assertEqual("korean", language)
            return "턍중쪽흉이", 91.7

        result = recognize_expected_player_name(
            image,
            "당옥쭉횽",
            recognizer=recognize,
        )

        self.assertEqual("당옥쭉횽", result.text)
        self.assertEqual("턍중쪽흉이", result.visual_observed)
        self.assertTrue(result.verified)
        self.assertEqual("korean_visual_constrained", result.strategy)


if __name__ == "__main__":
    unittest.main()
