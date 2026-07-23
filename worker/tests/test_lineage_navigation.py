import os
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game_executor.executor.lineage_classic.navigation import (
    ClientWindow,
    LineageSessionNavigator,
    NavigationError,
    TargetRegion,
    TemplateVision,
    Ui,
    WINDOW_TITLE_RE,
    region_text_matches,
)
from game_executor.executor.lineage_classic.paddle_ocr import (
    build_paddle_ocr_engine,
    paddle_ocr_boxes,
    paddle_ocr_text,
)
from game_executor.executor.lineage_classic.policy import trade_timeout_seconds
from game_executor.executor.lineage_classic.executor import (
    LineageClassicExecutor,
    TradeUi,
    buyer_ocr_action,
    customer_name_prefix_matches,
    region_center,
)
from game_executor.status import RuntimeStatus


ORDER = {
    "game_id": 1,
    "region_id": 12,
    "region_name": "冥王哈迪斯",
    "region_code": "아툰",
    "region_sort_order": 11,
    "region_select_page": 1,
    "region_select_x": 310,
    "region_select_y": 154,
    "asset_type": "adena",
    "asset_amount": 1000000,
    "details": [{
        "item_id": 1,
        "item_name": "Adena",
        "quantity": 1,
        "recognition_image_unselected_url": "/uploads/images/adena.png",
        "recognition_image_selected_url": "/uploads/images/adena-selected.png",
    }],
}


def _instant_navigator(vision):
    return SimpleNamespace(
        vision=vision,
        wait_for_step=lambda _name, predicate, **_kwargs: predicate(),
    )


class RuntimeProbeTest(unittest.TestCase):
    def test_minimized_window_is_restored_before_runtime_probe(self):
        window = mock.Mock()
        window.client_size.return_value = (0, 0)
        window.restore.return_value = (800, 600)
        runtime = RuntimeStatus()
        executor = LineageClassicExecutor(mock.Mock(), runtime)
        navigator = mock.Mock()
        navigator._is_in_game.return_value = True

        with mock.patch(
            "game_executor.executor.lineage_classic.executor.ClientWindow.find",
            return_value=window,
        ), mock.patch(
            "game_executor.executor.lineage_classic.executor.TemplateVision"
        ), mock.patch(
            "game_executor.executor.lineage_classic.executor.LineageSessionNavigator",
            return_value=navigator,
        ), mock.patch("builtins.print") as output:
            ready = executor.probe_runtime()

        self.assertTrue(ready)
        window.restore.assert_called_once()
        window.focus.assert_called_once()
        window.validate_size.assert_called_once_with((800, 600))
        self.assertEqual("logged_in", runtime.snapshot()["client_status"])
        self.assertEqual("ready", runtime.snapshot()["ui_health"])
        self.assertTrue(any("已自动恢复" in call.args[0] for call in output.call_args_list))

    def test_minimized_window_stays_recoverable_when_restore_needs_more_time(self):
        window = mock.Mock()
        window.client_size.return_value = (0, 0)
        window.restore.return_value = (0, 0)
        runtime = RuntimeStatus()
        executor = LineageClassicExecutor(mock.Mock(), runtime)

        with mock.patch(
            "game_executor.executor.lineage_classic.executor.ClientWindow.find",
            return_value=window,
        ), mock.patch("builtins.print") as output:
            ready = executor.probe_runtime()

        self.assertFalse(ready)
        self.assertEqual("not_ready", runtime.snapshot()["client_status"])
        self.assertEqual("recoverable", runtime.snapshot()["ui_health"])
        self.assertTrue(any("下次心跳重试" in call.args[0] for call in output.call_args_list))

    def test_restored_window_stays_recoverable_when_focus_is_temporarily_denied(self):
        window = mock.Mock()
        window.client_size.return_value = (0, 0)
        window.restore.return_value = (800, 600)
        window.focus.side_effect = NavigationError("Windows 暂时拒绝前台切换")
        runtime = RuntimeStatus()
        executor = LineageClassicExecutor(mock.Mock(), runtime)

        with mock.patch(
            "game_executor.executor.lineage_classic.executor.ClientWindow.find",
            return_value=window,
        ), mock.patch("builtins.print") as output:
            ready = executor.probe_runtime()

        self.assertFalse(ready)
        self.assertEqual("not_ready", runtime.snapshot()["client_status"])
        self.assertEqual("recoverable", runtime.snapshot()["ui_health"])
        self.assertTrue(any("无法切换到前台" in call.args[0] for call in output.call_args_list))

    def test_client_window_restore_waits_for_nonzero_client_size(self):
        window = ClientWindow(123, "Lineage Classic - 1.0 [LIVE] - Login [account]")
        fake_gui = mock.Mock()
        fake_gui.IsIconic.side_effect = [True, False, False]
        fake_gui.GetClientRect.side_effect = [
            (0, 0, 0, 0),
            (0, 0, 800, 600),
        ]
        fake_con = SimpleNamespace(SW_RESTORE=9)

        with mock.patch(
            "game_executor.executor.lineage_classic.navigation.win32gui", fake_gui
        ), mock.patch(
            "game_executor.executor.lineage_classic.navigation.win32con", fake_con
        ):
            size = window.restore(timeout=0.1)

        self.assertEqual((800, 600), size)
        fake_gui.ShowWindowAsync.assert_called_once_with(123, 9)

    def test_client_window_restore_uses_fallback_strategies(self):
        window = ClientWindow(123, "Lineage Classic - 1.0 [LIVE] - Login [account]")
        fake_gui = mock.Mock()
        fake_gui.IsIconic.side_effect = [True, False]
        fake_gui.ShowWindowAsync.side_effect = OSError("async restore rejected")
        fake_con = SimpleNamespace(SW_RESTORE=9, WM_SYSCOMMAND=0x0112, SC_RESTORE=0xF120)

        with mock.patch.object(
            window, "client_size", return_value=(0, 0)
        ), mock.patch.object(
            window, "_wait_for_restored_size", side_effect=[(0, 0), (800, 600)]
        ), mock.patch(
            "game_executor.executor.lineage_classic.navigation.win32gui", fake_gui
        ), mock.patch(
            "game_executor.executor.lineage_classic.navigation.win32con", fake_con
        ):
            size = window.restore(timeout=0.2)

        self.assertEqual((800, 600), size)
        fake_gui.PostMessage.assert_called_once_with(123, 0x0112, 0xF120, 0)
        fake_gui.ShowWindow.assert_called_once_with(123, 9)

    def test_client_window_restore_failure_mentions_matching_admin_privileges(self):
        window = ClientWindow(123, "Lineage Classic - 1.0 [LIVE] - Login [account]")
        fake_gui = mock.Mock()
        fake_gui.IsIconic.return_value = True
        denied = PermissionError("access denied")
        fake_gui.ShowWindowAsync.side_effect = denied
        fake_gui.PostMessage.side_effect = denied
        fake_gui.ShowWindow.side_effect = denied
        fake_con = SimpleNamespace(SW_RESTORE=9, WM_SYSCOMMAND=0x0112, SC_RESTORE=0xF120)

        with mock.patch.object(
            window, "client_size", return_value=(0, 0)
        ), mock.patch(
            "game_executor.executor.lineage_classic.navigation.win32gui", fake_gui
        ), mock.patch(
            "game_executor.executor.lineage_classic.navigation.win32con", fake_con
        ), self.assertRaisesRegex(NavigationError, "管理员身份"):
            window.restore(timeout=0.2)


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
        Ui.MENU_BUTTON: (775, 70),
        Ui.EXIT_PANEL_TRIGGER: (745, 90),
        Ui.RELOGIN_BUTTON: (700, 160),
        Ui.CHARACTER_SCREEN: (350, 90),
        Ui.CHARACTER_EXIT: (100, 380),
        Ui.CHARACTER_LOGIN: (350, 380),
        Ui.SERVER_SCREEN: (390, 117),
        Ui.SERVER_CONFIRM: (500, 410),
        Ui.INVENTORY_BUTTON: (750, 300),
    }

    def __init__(
        self,
        state="game",
        current_text="别的大区",
        inventory_open=False,
        server_text=None,
        ocr_point=(310, 154),
        item_points=None,
    ):
        self.state = state
        self.current_text = current_text
        self.inventory_open = inventory_open
        self.menu_open = False
        self.exit_panel_open = False
        self.server_selected = False
        self.character_selected = False
        self.server_text = server_text or ORDER["region_code"]
        self.ocr_point = ocr_point
        self.find_text_calls = 0
        self.item_points = item_points or {
            "/uploads/images/adena.png": (680, 200),
            "/uploads/images/adena-selected.png": (680, 200),
        }
        self.find_image_calls = []

    def find(self, template, _region, threshold=0.84):
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
        return None

    def pixel(self, _point):
        return (20, 20, 20) if self.character_selected else (0, 0, 0)

    def read_text(self, _region):
        if self.state == "game":
            return self.current_text
        if self.state == "server":
            return self.server_text
        return ""

    def find_text(self, _target, _region):
        self.find_text_calls += 1
        return self.ocr_point

    def find_image(self, image_source, _region, threshold=0.90):
        self.find_image_calls.append((image_source, threshold))
        return self.item_points.get(image_source) if self.inventory_open else None

    def clicked(self, point):
        # 正式输入层会在模板中心附近选择安全落点，测试状态机按同样容差处理。
        for center in self.CENTERS.values():
            if abs(point[0] - center[0]) <= 3 and abs(point[1] - center[1]) <= 3:
                point = center
                break
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
    def test_screen_step_wait_uses_business_delay_and_three_detection_attempts(self):
        sleeps = []
        random_ranges = []
        outcomes = iter([False, False, (320, 180)])
        navigator = LineageSessionNavigator(
            mock.Mock(),
            _Window(),
            mock.Mock(),
            sleep=sleeps.append,
            random_uniform=lambda low, high: (
                random_ranges.append((low, high)) or 7.0
            ),
        )

        with mock.patch("builtins.print") as output:
            result = navigator.wait_for_step(
                "进入新画面",
                lambda: next(outcomes),
                profile="screen",
            )

        self.assertEqual((320, 180), result)
        self.assertEqual([(3.0, 10.0)], random_ranges)
        # 画面切换：固定 3 + 随机 7，前两次未就绪各等待 2 秒。
        self.assertAlmostEqual(14.0, sum(sleeps), places=5)
        self.assertTrue(any("第 3/3 次 已就绪" in call.args[0] for call in output.call_args_list))

    def test_failed_step_only_reports_error_after_three_checks(self):
        checks = 0
        navigator = LineageSessionNavigator(
            mock.Mock(),
            _Window(),
            mock.Mock(),
            sleep=lambda _seconds: None,
            random_uniform=lambda low, _high: low,
        )

        def not_ready():
            nonlocal checks
            checks += 1
            return None

        with mock.patch("builtins.print") as output:
            result = navigator.wait_for_step(
                "等待按钮",
                not_ready,
                profile="panel",
            )

        self.assertIsNone(result)
        self.assertEqual(3, checks)
        self.assertTrue(any("连续 3 次检测" in call.args[0] for call in output.call_args_list))

    def test_item_drag_delay_is_shorter_than_screen_transition(self):
        screen_sleeps = []
        item_sleeps = []
        screen = LineageSessionNavigator(
            mock.Mock(), _Window(), mock.Mock(),
            sleep=screen_sleeps.append,
            random_uniform=lambda _low, high: high,
        )
        item = LineageSessionNavigator(
            mock.Mock(), _Window(), mock.Mock(),
            sleep=item_sleeps.append,
            random_uniform=lambda _low, high: high,
        )

        with mock.patch("builtins.print"):
            screen.wait_after_step("切换画面", profile="screen")
            item.wait_after_step("拖拽物品", profile="item_drag")

        self.assertAlmostEqual(13.0, sum(screen_sleeps), places=5)
        self.assertAlmostEqual(1.4, sum(item_sleeps), places=5)
        self.assertGreater(sum(screen_sleeps), sum(item_sleeps) * 5)

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

    def test_trade_region_click_varies_only_inside_button_safe_area(self):
        vision = _Vision()
        hardware = _Hardware(vision)
        navigator = LineageSessionNavigator(
            hardware, _Window(), vision, sleep=lambda _seconds: None
        )

        for _ in range(20):
            navigator.click_region(TradeUi.REQUEST_ACCEPT_REGION)

        self.assertTrue(all(530 <= x <= 544 for x, _y in hardware.moves))
        self.assertTrue(all(549 <= y <= 553 for _x, y in hardware.moves))

    def test_customer_name_uses_expected_prefix_and_allows_korean_particles(self):
        self.assertTrue(customer_name_prefix_matches("홍길동이", "홍길동"))
        self.assertTrue(customer_name_prefix_matches("홍길동가", "홍길동"))
        self.assertTrue(customer_name_prefix_matches("홍길동이[가]", "홍길동"))
        self.assertTrue(customer_name_prefix_matches("Buyer 27 이", "buyer27"))
        self.assertFalse(customer_name_prefix_matches("홍길순이", "홍길동"))
        self.assertFalse(customer_name_prefix_matches("", "홍길동"))

    def test_item_transfers_use_images_sent_with_order(self):
        executor = LineageClassicExecutor(object())
        vision = _Vision(
            inventory_open=True,
            item_points={"/images/red.png": (620, 80), "/images/blue.png": (660, 80)},
        )
        order = {
            "asset_type": "item",
            "details": [
                {"item_id": 11, "item_name": "红水", "quantity": 3,
                 "recognition_image_unselected_url": "/images/red.png",
                 "recognition_image_selected_url": "/images/red-selected.png"},
                {"item_id": 12, "item_name": "蓝水", "quantity": 2,
                 "recognition_image_unselected_url": "/images/blue.png",
                 "recognition_image_selected_url": "/images/blue-selected.png"},
            ],
        }

        transfers = executor._build_transfers(order, _instant_navigator(vision))

        self.assertEqual([((620, 80), 3), ((660, 80), 2)], [
            (transfer.source, transfer.quantity) for transfer in transfers
        ])

    def test_gold_uses_database_image_and_asset_amount(self):
        executor = LineageClassicExecutor(object())
        vision = _Vision(
            inventory_open=True,
            item_points={"/images/adena-selected.png": (680, 200)},
        )
        order = {
            "asset_type": "adena",
            "asset_amount": 1000000,
            "details": [{
                "item_id": 1,
                "item_name": "Adena",
                "quantity": 1,
                "recognition_image_unselected_url": "/images/adena.png",
                "recognition_image_selected_url": "/images/adena-selected.png",
            }],
        }

        transfers = executor._build_transfers(order, _instant_navigator(vision))

        self.assertEqual([((680, 200), 1000000)], [
            (transfer.source, transfer.quantity) for transfer in transfers
        ])

    def test_item_missing_selected_recognition_image_is_rejected(self):
        executor = LineageClassicExecutor(object())
        order = {
            "asset_type": "item",
            "details": [{
                "item_id": 11,
                "item_name": "红水",
                "quantity": 3,
                "recognition_image_unselected_url": "/images/red.png",
            }],
        }

        with self.assertRaisesRegex(NavigationError, "缺少选中状态识别图片"):
            executor._build_transfers(
                order, _instant_navigator(_Vision(inventory_open=True))
            )

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
            Ui.INVENTORY_BUTTON,
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

    def test_dynamic_item_template_accepts_data_url_and_is_cached(self):
        try:
            vision = TemplateVision(_Window())
        except Exception as exc:
            self.skipTest(str(exc))
        data_url = (
            "data:image/png;base64,"
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwC"
            "AAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
        )

        first = vision._dynamic_template(data_url)
        second = vision._dynamic_template(data_url)

        self.assertIs(first, second)
        self.assertEqual((1, 1), first.shape[:2])

    def test_window_title_extracts_version_and_login_account(self):
        match = WINDOW_TITLE_RE.search(
            "Lineage Classic - 26.07.15.2001 [LIVE] - Login [jyz27a@gmail.com]"
        )
        self.assertIsNotNone(match)
        self.assertEqual("26.07.15.2001", match.group("version"))
        self.assertEqual("jyz27a@gmail.com", match.group("account"))

    def test_target_region_uses_coordinates_from_central_order(self):
        target = TargetRegion.from_order(ORDER)
        self.assertEqual((310, 154), (target.select_x, target.select_y))
        self.assertEqual(1, target.select_page)

    def test_target_region_allows_no_coordinates_but_rejects_partial_or_out_of_bounds(self):
        missing = {key: value for key, value in ORDER.items() if key != "region_select_x"}
        with self.assertRaises(NavigationError):
            TargetRegion.from_order(missing)
        with self.assertRaises(NavigationError):
            TargetRegion.from_order({**ORDER, "region_select_x": 800})
        without_coordinates = {
            key: value for key, value in ORDER.items()
            if key not in {"region_select_x", "region_select_y"}
        }
        target = TargetRegion.from_order(without_coordinates)
        self.assertIsNone(target.select_x)
        self.assertIsNone(target.select_y)

    def test_target_region_rejects_invalid_page_number(self):
        with self.assertRaisesRegex(NavigationError, "页码"):
            TargetRegion.from_order({**ORDER, "region_select_page": 0})

    def test_server_selection_prefers_exact_central_coordinate_without_ocr(self):
        vision = _Vision(state="server", server_text="켄라우헬", ocr_point=None)
        hardware = _Hardware(vision)
        navigator = LineageSessionNavigator(
            hardware, _Window(), vision, sleep=lambda _seconds: None
        )

        navigator._select_server(TargetRegion.from_order(ORDER))

        self.assertLessEqual(abs(ORDER["region_select_x"] - hardware.moves[0][0]), 3)
        self.assertLessEqual(abs(ORDER["region_select_y"] - hardware.moves[0][1]), 3)
        self.assertEqual(0, vision.find_text_calls)
        self.assertEqual("character", vision.state)

    def test_server_selection_falls_back_to_ocr_when_coordinate_is_missing(self):
        order = {
            key: value for key, value in ORDER.items()
            if key not in {"region_select_x", "region_select_y"}
        }
        vision = _Vision(state="server", ocr_point=(470, 173))
        hardware = _Hardware(vision)
        navigator = LineageSessionNavigator(
            hardware, _Window(), vision, sleep=lambda _seconds: None
        )

        navigator._select_server(TargetRegion.from_order(order))

        self.assertLessEqual(abs(470 - hardware.moves[0][0]), 3)
        self.assertLessEqual(abs(173 - hardware.moves[0][1]), 3)
        self.assertEqual(1, vision.find_text_calls)

    def test_server_selection_without_coordinate_stops_when_ocr_finds_nothing(self):
        order = {
            key: value for key, value in ORDER.items()
            if key not in {"region_select_x", "region_select_y"}
        }
        vision = _Vision(state="server", ocr_point=None)
        hardware = _Hardware(vision)
        navigator = LineageSessionNavigator(
            hardware, _Window(), vision, sleep=lambda _seconds: None
        )

        with self.assertRaisesRegex(NavigationError, "OCR 也未找到"):
            navigator._select_server(TargetRegion.from_order(order))

        self.assertEqual([], hardware.moves)

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

    def test_paddle_ocr_extracts_text_box_centers(self):
        boxes = paddle_ocr_boxes([{
            "res": {
                "rec_texts": ["아툰"],
                "rec_scores": [0.974],
                "rec_polys": [[[40, 20], [120, 20], [120, 44], [40, 44]]],
            }
        }])

        self.assertEqual(1, len(boxes))
        self.assertEqual("아툰", boxes[0].text)
        self.assertAlmostEqual(97.4, boxes[0].confidence)
        self.assertEqual((80.0, 32.0), boxes[0].center)

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

    def test_same_region_still_reselects_region_before_opening_inventory(self):
        vision = _Vision(current_text=ORDER["region_code"], inventory_open=False)
        window = _Window()
        navigator = LineageSessionNavigator(
            _Hardware(vision), window, vision, sleep=lambda _seconds: None
        )

        target = navigator.ensure_target_region(ORDER)

        self.assertEqual(ORDER["region_id"], target.region_id)
        self.assertTrue(vision.menu_open)
        self.assertTrue(vision.exit_panel_open)
        self.assertTrue(vision.character_selected)
        self.assertTrue(vision.inventory_open)
        self.assertEqual("game", vision.state)
        self.assertTrue(window.focused)
        self.assertTrue(window.validated)

    def test_switch_region_uses_menu_fallback_and_returns_to_game(self):
        vision = _Vision(current_text="켄라우헬", inventory_open=False)
        hardware = _Hardware(vision)
        navigator = LineageSessionNavigator(
            hardware, _Window(), vision, sleep=lambda _seconds: None
        )

        navigator.ensure_target_region(ORDER)

        self.assertTrue(vision.menu_open)
        self.assertTrue(vision.exit_panel_open)
        self.assertTrue(vision.character_selected)
        self.assertTrue(vision.inventory_open)
        self.assertEqual("game", vision.state)
        server_clicks = [
            point for point in hardware.moves
            if abs(point[0] - ORDER["region_select_x"]) <= 3
            and abs(point[1] - ORDER["region_select_y"]) <= 3
        ]
        self.assertEqual(1, len(server_clicks))


if __name__ == "__main__":
    unittest.main()
