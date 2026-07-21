import os
import random
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trader.executor.lineage_classic.navigation import (
    LineageSessionNavigator,
    ServerListLayout,
    TargetRegion,
    TemplateVision,
    Ui,
    WINDOW_TITLE_RE,
    region_text_matches,
)
from trader.executor.lineage_classic.paddle_ocr import (
    build_paddle_ocr_engine,
    paddle_ocr_text,
)
from trader.executor.lineage_classic.policy import trade_timeout_seconds
from trader.executor.lineage_classic.executor import (
    LineageClassicExecutor,
    TradeUi,
    buyer_ocr_action,
    customer_name_prefix_matches,
    region_center,
)


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
    def test_buyer_ocr_at_90_or_above_auto_accepts_only_matching_name(self):
        self.assertEqual("accept", buyer_ocr_action("홍길동이", "홍길동", 90.0))
        self.assertEqual("review", buyer_ocr_action("홍길순", "홍길동", 99.0))

    def test_buyer_ocr_below_90_always_needs_human_review(self):
        self.assertEqual("review", buyer_ocr_action("홍길동", "홍길동", 89.9))
        self.assertEqual("review", buyer_ocr_action("", "홍길동", -1.0))

    def test_trade_fixed_action_regions_use_the_provided_centers(self):
        self.assertEqual((537, 551), region_center(TradeUi.REQUEST_ACCEPT_REGION))
        self.assertEqual((568, 551), region_center(TradeUi.REQUEST_REJECT_REGION))
        self.assertEqual((537, 551), region_center(TradeUi.FINAL_ACCEPT_REGION))
        self.assertEqual((568, 551), region_center(TradeUi.FINAL_REJECT_REGION))

    def test_customer_name_uses_expected_prefix_and_allows_korean_particles(self):
        self.assertTrue(customer_name_prefix_matches("홍길동이", "홍길동"))
        self.assertTrue(customer_name_prefix_matches("홍길동가", "홍길동"))
        self.assertTrue(customer_name_prefix_matches("홍길동이[가]", "홍길동"))
        self.assertTrue(customer_name_prefix_matches("Buyer 27 이", "buyer27"))
        self.assertFalse(customer_name_prefix_matches("홍길순이", "홍길동"))
        self.assertFalse(customer_name_prefix_matches("", "홍길동"))

    def test_item_transfers_use_detail_quantities_and_inventory_positions(self):
        executor = LineageClassicExecutor(object())
        order = {
            "asset_type": "item",
            "details": [
                {"item_id": 11, "item_name": "红水", "quantity": 3},
                {"item_id": 12, "item_name": "蓝水", "quantity": 2},
            ],
            "item_positions": [
                {"item_id": 11, "x": 620, "y": 80},
                {"item_id": 12, "x": 660, "y": 80},
            ],
        }

        transfers = executor._build_transfers(order, object())

        self.assertEqual([((620, 80), 3), ((660, 80), 2)], [
            (transfer.source, transfer.quantity) for transfer in transfers
        ])

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

    def test_paddle_ocr_returns_lowest_token_confidence_on_0_to_100_scale(self):
        text, confidence = paddle_ocr_text([{
            "res": {
                "rec_texts": ["아툰", "서버"],
                "rec_scores": [0.962, 0.899],
            }
        }])
        self.assertEqual("아툰 서버", text)
        self.assertEqual(89.9, confidence)

    def test_paddle_ocr_reads_result_json_property(self):
        class Result:
            json = {"res": {"rec_texts": ["아툰"], "rec_scores": [0.974]}}

        text, confidence = paddle_ocr_text([Result()])
        self.assertEqual("아툰", text)
        self.assertAlmostEqual(97.4, confidence)

    def test_paddle_ocr_engine_is_forced_to_cpu(self):
        calls = []

        class FakePaddleOCR:
            def __init__(self, **kwargs):
                calls.append(kwargs)

        with mock.patch.dict(
            sys.modules,
            {"paddleocr": type("Module", (), {"PaddleOCR": FakePaddleOCR})},
        ):
            build_paddle_ocr_engine()

        self.assertEqual("cpu", calls[0]["device"])
        self.assertFalse(calls[0]["enable_mkldnn"])
        self.assertEqual("PP-OCRv5_mobile_det", calls[0]["text_detection_model_name"])
        self.assertEqual(
            "korean_PP-OCRv5_mobile_rec",
            calls[0]["text_recognition_model_name"],
        )

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
