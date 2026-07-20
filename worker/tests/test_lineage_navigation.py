import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trader.executor.lineage_classic.navigation import (
    LineageSessionNavigator,
    ServerListLayout,
    TargetRegion,
    TemplateVision,
    Ui,
    WINDOW_TITLE_RE,
    confident_ocr_text,
    region_text_matches,
)
from trader.executor.lineage_classic.policy import trade_timeout_seconds
from trader.executor.lineage_classic.executor import TradeUi


ORDER = {
    "game_id": 1,
    "region_id": 12,
    "region_name": "冥王哈迪斯",
    "region_code": "아툰",
    "region_sort_order": 11,
}


class _Window:
    def __init__(self):
        self.focused = False
        self.validated = False

    def focus(self):
        self.focused = True

    def validate_size(self):
        self.validated = True

    def client_origin(self):
        return 100, 50


class _Hardware:
    def __init__(self, vision):
        self.vision = vision
        self.moves = []
        self.current = None

    def mouse_move(self, x, y, **_kwargs):
        self.current = (x - 100, y - 50)
        self.moves.append(self.current)
        return True

    def mouse_click(self):
        self.vision.clicked(self.current)
        return True


class _Vision:
    CENTERS = {
        Ui.IN_GAME: (95, 459),
        Ui.MENU_BUTTON: (775, 70),
        Ui.EXIT_PANEL_TRIGGER: (745, 90),
        Ui.RELOGIN_BUTTON: (700, 160),
        Ui.CHARACTER_SCREEN: (350, 90),
        Ui.CHARACTER_EXIT: (100, 380),
        Ui.CHARACTER_LOGIN: (350, 380),
        Ui.SERVER_SCREEN: (390, 117),
        Ui.SERVER_CONFIRM: (500, 410),
        Ui.INVENTORY_BUTTON: (750, 300),
        Ui.GOLD_TEMPLATES[0]: (680, 200),
    }

    def __init__(self, state="game", current_text="别的大区", inventory_open=False):
        self.state = state
        self.current_text = current_text
        self.inventory_open = inventory_open
        self.menu_open = False
        self.exit_panel_open = False
        self.server_selected = False
        self.character_selected = False

    def find(self, template, _region, threshold=0.84):
        if template == Ui.IN_GAME:
            return self.CENTERS[template] if self.state == "game" else None
        if template == Ui.CHARACTER_SCREEN:
            return self.CENTERS[template] if self.state == "character" else None
        if template == Ui.SERVER_SCREEN:
            return self.CENTERS[template] if self.state == "server" else None
        if template == Ui.MENU_BUTTON:
            return self.CENTERS[template] if self.state == "game" and not self.menu_open else None
        if template == Ui.EXIT_PANEL_TRIGGER:
            return self.CENTERS[template] if self.menu_open and not self.exit_panel_open else None
        if template == Ui.RELOGIN_BUTTON:
            return self.CENTERS[template] if self.exit_panel_open else None
        if template == Ui.CHARACTER_EXIT:
            return self.CENTERS[template] if self.state == "character" else None
        if template == Ui.SERVER_CONFIRM:
            return self.CENTERS[template] if self.state == "server" and self.server_selected else None
        if template == Ui.CHARACTER_LOGIN:
            return self.CENTERS[template] if self.state == "character" else None
        if template == Ui.INVENTORY_BUTTON:
            return self.CENTERS[template] if self.state == "game" and not self.inventory_open else None
        if template in Ui.GOLD_TEMPLATES:
            return self.CENTERS[Ui.GOLD_TEMPLATES[0]] if self.inventory_open else None
        return None

    def pixel(self, _point):
        return (20, 20, 20) if self.character_selected else (0, 0, 0)

    def read_text(self, _region):
        return self.current_text if self.state == "game" else ""

    def clicked(self, point):
        if point == self.CENTERS[Ui.MENU_BUTTON]:
            self.menu_open = True
        elif point == self.CENTERS[Ui.EXIT_PANEL_TRIGGER]:
            self.exit_panel_open = True
        elif point == self.CENTERS[Ui.RELOGIN_BUTTON]:
            self.state = "character"
        elif point == self.CENTERS[Ui.CHARACTER_EXIT]:
            self.state = "server"
        elif self.state == "server" and point not in self.CENTERS.values():
            self.server_selected = True
        elif point == self.CENTERS[Ui.SERVER_CONFIRM]:
            self.state = "character"
        elif self.state == "character" and point[0] in range(136, 226) and point[1] in range(57, 295):
            self.character_selected = True
        elif point == self.CENTERS[Ui.CHARACTER_LOGIN]:
            self.state = "game"
            self.current_text = ORDER["region_code"]
        elif point == self.CENTERS[Ui.INVENTORY_BUTTON]:
            self.inventory_open = True


class LineageNavigationTest(unittest.TestCase):
    def test_trade_timeout_uses_order_value_and_safe_bounds(self):
        self.assertEqual(300, trade_timeout_seconds({}))
        self.assertEqual(600, trade_timeout_seconds({"trade_timeout_seconds": 600}))
        self.assertEqual(30, trade_timeout_seconds({"trade_timeout_seconds": 1}))
        self.assertEqual(7200, trade_timeout_seconds({"trade_timeout_seconds": 99999}))

    def test_all_navigation_templates_can_be_loaded_from_unicode_paths(self):
        try:
            vision = TemplateVision(_Window())
        except Exception as exc:
            self.skipTest(str(exc))
        templates = (
            *Ui.GOLD_TEMPLATES,
            Ui.INVENTORY_BUTTON,
            Ui.IN_GAME,
            Ui.MENU_BUTTON,
            Ui.EXIT_PANEL_TRIGGER,
            Ui.RELOGIN_BUTTON,
            Ui.CHARACTER_SCREEN,
            Ui.CHARACTER_EXIT,
            Ui.CHARACTER_LOGIN,
            Ui.SERVER_SCREEN,
            Ui.SERVER_CONFIRM,
            TradeUi.REQUEST_TEMPLATE,
            TradeUi.CONFIRM_BUTTON_TEMPLATE,
            TradeUi.CANCEL_BUTTON_TEMPLATE,
            TradeUi.FINAL_CONFIRM_TEMPLATE,
        )
        for template in templates:
            self.assertIsNotNone(vision._template(template))

    def test_window_title_extracts_version_and_login_account(self):
        match = WINDOW_TITLE_RE.search(
            "Lineage Classic - 26.07.15.2001 [LIVE] - Login [jyz27a@gmail.com]"
        )
        self.assertIsNotNone(match)
        self.assertEqual("26.07.15.2001", match.group("version"))
        self.assertEqual("jyz27a@gmail.com", match.group("account"))

    def test_server_points_follow_two_column_order(self):
        self.assertEqual((310, 154), tuple(vars(ServerListLayout.point(1)).values()))
        self.assertEqual((470, 154), tuple(vars(ServerListLayout.point(2)).values()))
        self.assertEqual((310, 173), tuple(vars(ServerListLayout.point(3)).values()))
        self.assertEqual((310, 413), tuple(vars(ServerListLayout.point(29)).values()))

    def test_server_point_jitter_stays_within_required_bounds(self):
        base = ServerListLayout.point(11)
        rng = random.Random(7)
        for _ in range(100):
            point = ServerListLayout.jittered_point(11, rng)
            self.assertLessEqual(abs(point.x - base.x), 30)
            self.assertLessEqual(abs(point.y - base.y), 3)

    def test_ocr_matches_name_or_korean_code(self):
        target = TargetRegion.from_order(ORDER)
        self.assertTrue(region_text_matches("아 툰", target))
        self.assertTrue(region_text_matches("冥王 哈迪斯", target))
        self.assertFalse(region_text_matches("아", target))
        self.assertFalse(region_text_matches("켄라우헬", target))

    def test_ocr_rejects_entire_result_when_any_token_is_below_threshold(self):
        text, confidence = confident_ocr_text(
            {"text": ["아툰", "서버"], "conf": ["96.2", "89.9"]},
            minimum_confidence=90,
        )
        self.assertEqual("", text)
        self.assertEqual(89.9, confidence)

    def test_ocr_accepts_only_when_all_tokens_have_high_confidence(self):
        text, confidence = confident_ocr_text(
            {"text": ["아툰"], "conf": ["97.4"]},
            minimum_confidence=90,
        )
        self.assertEqual("아툰", text)
        self.assertEqual(97.4, confidence)

    def test_same_region_only_opens_inventory(self):
        vision = _Vision(current_text=ORDER["region_code"], inventory_open=False)
        window = _Window()
        navigator = LineageSessionNavigator(
            _Hardware(vision), window, vision, rng=random.Random(1), sleep=lambda _seconds: None
        )

        target = navigator.ensure_target_region(ORDER)

        self.assertEqual(ORDER["region_id"], target.region_id)
        self.assertTrue(vision.inventory_open)
        self.assertEqual("game", vision.state)
        self.assertTrue(window.focused)
        self.assertTrue(window.validated)

    def test_switch_region_uses_menu_fallback_and_returns_to_game(self):
        vision = _Vision(current_text="켄라우헬", inventory_open=False)
        hardware = _Hardware(vision)
        navigator = LineageSessionNavigator(
            hardware, _Window(), vision, rng=random.Random(3), sleep=lambda _seconds: None
        )

        navigator.ensure_target_region(ORDER)

        self.assertTrue(vision.menu_open)
        self.assertTrue(vision.exit_panel_open)
        self.assertTrue(vision.character_selected)
        self.assertTrue(vision.inventory_open)
        self.assertEqual("game", vision.state)
        base = ServerListLayout.point(ORDER["region_sort_order"])
        server_clicks = [
            point for point in hardware.moves
            if abs(point[0] - base.x) <= 30 and abs(point[1] - base.y) <= 3
        ]
        self.assertEqual(1, len(server_clicks))


if __name__ == "__main__":
    unittest.main()
