import inspect
import os
import sys
import tempfile
import threading
import unittest
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game_executor.executor.lineage_classic.navigation import (
    ClientWindow,
    LineageSessionNavigator,
    NavigationError,
    RegionSessionCache,
    RegionSessionKey,
    TargetRegion,
    TemplateVision,
    Ui,
    WINDOW_TITLE_RE,
    region_text_matches,
)
import game_executor.executor.lineage_classic.navigation as lineage_navigation
from game_executor.executor.lineage_classic.paddle_ocr import (
    build_paddle_ocr_engine,
    build_text_recognition_engine,
    paddle_ocr_boxes,
    paddle_ocr_text,
)
from game_executor.executor.lineage_classic.policy import (
    buyer_poll_schedule,
    trade_timeout_seconds,
)
from game_executor.executor.lineage_classic.executor import (
    LineageClassicExecutor,
    TradeUi,
    buyer_ocr_action,
    customer_name_prefix_matches,
    random_region_point,
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


@unittest.skipIf(
    lineage_navigation.Image is None or lineage_navigation.np is None,
    "Pillow/numpy not installed",
)
class ActionVisualizationTest(unittest.TestCase):
    def test_drag_and_keyboard_actions_create_distinct_annotated_images(self):
        vision = object.__new__(TemplateVision)
        vision._recent_match_visuals = []
        vision._debug_image_sequence = 0
        vision._capture = mock.Mock(return_value=lineage_navigation.np.zeros(
            (600, 800, 3),
            dtype=lineage_navigation.np.uint8,
        ))

        drag_action = {
            "action": "mouse_drag",
            "client_target_start": [630, 180],
            "client_target_end": [420, 310],
            "client_actual_start": [631, 179],
            "client_actual_end": [417, 314],
            "client_start_action_bounds": [628, 178, 632, 182],
            "client_end_action_bounds": [414, 304, 426, 316],
        }
        keyboard_action = {
            "action": "key_type",
            "text": "250000",
            "typing_plan": [
                {"key": key, "hold_ms": 60, "gap_ms": 40}
                for key in "250000"
            ],
        }

        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.object(
            lineage_navigation,
            "ACTION_DEBUG_IMAGE_DIR",
            lineage_navigation.Path(temp_dir),
        ):
            drag_path = vision.save_action_visualization(drag_action)
            keyboard_path = vision.save_action_visualization(keyboard_action)

            self.assertIsNotNone(drag_path)
            self.assertIsNotNone(keyboard_path)
            self.assertNotEqual(drag_path, keyboard_path)
            with lineage_navigation.Image.open(drag_path) as drag_image:
                self.assertEqual((800, 600), drag_image.size)
                drag_colors = {
                    color
                    for _count, color in drag_image.getcolors(maxcolors=1_000_000)
                }
                self.assertIn((255, 0, 255), drag_colors)
            with lineage_navigation.Image.open(keyboard_path) as keyboard_image:
                self.assertEqual((800, 600), keyboard_image.size)
                keyboard_colors = {
                    color
                    for _count, color in keyboard_image.getcolors(maxcolors=1_000_000)
                }
                self.assertIn((235, 235, 235), keyboard_colors)


def _instant_navigator(vision):
    def find_inventory_item(images, *, label):
        for image in images:
            point = vision.find_image(
                image,
                Ui.INVENTORY_CONTENT_REGION,
                threshold=0.90,
            )
            if point is not None:
                return point
        return None

    return SimpleNamespace(
        vision=vision,
        wait_for_step=lambda _name, predicate, **_kwargs: predicate(),
        find_inventory_item=find_inventory_item,
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
        self.assertTrue(executor.runtime_recovery_pending())
        self.assertTrue(any("连接后的有限次数恢复重试" in call.args[0] for call in output.call_args_list))

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
        self.assertTrue(executor.runtime_recovery_pending())
        self.assertTrue(any("无法切换到前台" in call.args[0] for call in output.call_args_list))

    def test_visible_window_outside_game_waits_for_order_instead_of_claiming_recovery(self):
        window = mock.Mock()
        window.client_size.return_value = (800, 600)
        runtime = RuntimeStatus()
        executor = LineageClassicExecutor(mock.Mock(), runtime)
        executor._region_session_cache.remember(
            RegionSessionKey.from_order(
                ORDER,
                TargetRegion.from_order(ORDER),
            )
        )
        navigator = mock.Mock()
        navigator._is_in_game.return_value = False

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

        self.assertFalse(ready)
        self.assertFalse(executor.runtime_recovery_pending())
        self.assertIsNone(executor._region_session_cache.snapshot())
        self.assertEqual("recoverable", runtime.snapshot()["ui_health"])
        self.assertTrue(any(
            "将在收到交易任务后按订单信息恢复" in call.args[0]
            for call in output.call_args_list
        ))

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

    def test_client_origin_uses_game_area_origin_without_title_offset(self):
        window = ClientWindow(123, "Lineage Classic - 1.0 [LIVE] - Login [account]")
        fake_gui = mock.Mock()
        fake_gui.ClientToScreen.return_value = (190, 213)

        with mock.patch(
            "game_executor.executor.lineage_classic.navigation.win32gui", fake_gui
        ):
            origin = window.client_origin()

        self.assertEqual((190, 213), origin)
        fake_gui.ClientToScreen.assert_called_once_with(123, (0, 0))

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
    TEMPLATE_SIZES = {
        Ui.MENU_BUTTON: (9, 27),
        Ui.EXIT_PANEL_TRIGGER: (22, 28),
        Ui.RELOGIN_BUTTON: (80, 39),
        Ui.INVENTORY_OPEN: (27, 42),
    }
    CENTERS = {
        Ui.IN_GAME_ANCHOR: (98, 459),
        Ui.MENU_BUTTON: (794, 584),
        Ui.EXIT_PANEL_TRIGGER: (778, 584),
        Ui.RELOGIN_BUTTON: (693, 82),
        Ui.CHARACTER_SCREEN: (119, 368),
        Ui.CHARACTER_EXIT: (703, 537),
        Ui.CHARACTER_LOGIN: (700, 512),
        Ui.SERVER_SCREEN: (301, 132),
        Ui.ACCOUNT_CONFIRM_BUTTON: (642, 451),
        Ui.INVENTORY_BUTTON: (704, 585),
        Ui.INVENTORY_OPEN: (784, 337),
    }

    def __init__(
        self,
        state="game",
        current_text="别的大区",
        inventory_open=False,
        inventory_button_visible=True,
        server_text=None,
        ocr_point=(310, 154),
        page_points=None,
        item_points=None,
    ):
        self.state = state
        self.current_text = current_text
        self.inventory_open = inventory_open
        self.inventory_button_visible = inventory_button_visible
        self.menu_open = False
        self.exit_panel_open = False
        self.server_selected = False
        self.character_selected = False
        self.server_text = server_text or ORDER["region_code"]
        self.ocr_point = ocr_point
        self.find_text_calls = 0
        self.page_points = page_points or {
            1: (340, 353),
            2: (364, 353),
        }
        self.page_number_calls = []
        self.current_page = None
        self.inventory_refreshes = 0
        self.item_points = item_points or {
            "/uploads/images/adena.png": (680, 200),
            "/uploads/images/adena-selected.png": (680, 200),
        }
        self.find_image_calls = []
        self.find_calls = []
        self.bright_pixel_calls = []

    def find(self, template, region, threshold=0.84):
        self.find_calls.append((template, region, threshold))
        if template == Ui.IN_GAME_ANCHOR:
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
        if template == Ui.ACCOUNT_CONFIRM_BUTTON:
            return self.CENTERS[template] if self.state == "account_confirm" else None
        if template == Ui.CHARACTER_LOGIN:
            return self.CENTERS[template] if self.state == "character" else None
        if template == Ui.INVENTORY_BUTTON:
            return (
                self.CENTERS[template]
                if self.state == "game"
                and not self.inventory_open
                and self.inventory_button_visible
                else None
            )
        if template == Ui.INVENTORY_OPEN:
            return (
                self.CENTERS[template]
                if self.state == "game" and self.inventory_open
                else None
            )
        return None

    def template_size(self, template):
        return self.TEMPLATE_SIZES[template]

    def pixel(self, _point):
        return (20, 20, 20) if self.character_selected else (0, 0, 0)

    def bright_pixel_count(self, region, threshold):
        self.bright_pixel_calls.append((region, threshold))
        return 149 if self.character_selected else 0

    def read_text(self, _region):
        if self.state == "game":
            return self.current_text
        if self.state == "server":
            return self.server_text
        return ""

    def find_text(self, _target, _region):
        self.find_text_calls += 1
        return self.ocr_point

    def find_page_number(self, page, _region):
        self.page_number_calls.append(page)
        return self.page_points.get(page)

    def find_image(self, image_source, region, threshold=0.90):
        self.find_image_calls.append((image_source, region, threshold))
        return self.item_points.get(image_source) if self.inventory_open else None

    def clicked(self, point):
        # 正式输入层会在模板中心附近选择安全落点，测试状态机按同样容差处理。
        menu_left, menu_top, menu_right, menu_bottom = Ui.MENU_BUTTON_CLICK_REGION
        if (
            menu_left <= point[0] < menu_right
            and menu_top <= point[1] < menu_bottom
        ):
            self.menu_open = True
            return
        for page, center in self.page_points.items():
            if abs(point[0] - center[0]) <= 2 and abs(point[1] - center[1]) <= 2:
                self.current_page = page
                return
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
            self.state = "account_confirm"
        elif point == self.CENTERS[Ui.ACCOUNT_CONFIRM_BUTTON]:
            self.state = "character"
        elif self.state == "character" and point[0] in range(136, 226) and point[1] in range(57, 295):
            self.character_selected = True
        elif point == self.CENTERS[Ui.CHARACTER_LOGIN]:
            self.state = "game"
            self.current_text = ORDER["region_code"]
        elif point == self.CENTERS[Ui.INVENTORY_BUTTON]:
            self.inventory_open = not self.inventory_open
            if self.inventory_open:
                self.inventory_refreshes += 1


class LineageNavigationTest(unittest.TestCase):
    def test_step_verification_polling_is_fixed_at_thirty_attempts(self):
        self.assertEqual(30, lineage_navigation.STEP_VERIFY_ATTEMPTS)

    def test_in_game_detection_uses_dedicated_status_bar_anchor_first(self):
        vision = mock.Mock()
        vision.find.side_effect = lambda template, *_args: (
            (98, 459) if template == Ui.IN_GAME_ANCHOR else None
        )
        navigator = LineageSessionNavigator(
            mock.Mock(),
            _Window(),
            vision,
            sleep=lambda _seconds: None,
        )

        self.assertTrue(navigator._is_in_game())
        vision.find.assert_called_once_with(
            Ui.IN_GAME_ANCHOR,
            Ui.IN_GAME_ANCHOR_REGION,
            0.72,
        )
        self.assertEqual((200, 465, 300, 500), Ui.IN_GAME_ANCHOR_REGION)

    def test_inventory_uses_separate_content_and_bottom_button_regions(self):
        vision = _Vision(inventory_open=False)
        navigator = LineageSessionNavigator(
            _Hardware(vision),
            _Window(),
            vision,
            sleep=lambda _seconds: None,
        )

        with mock.patch("builtins.print") as output:
            navigator.ensure_inventory_open()
            navigator.ensure_inventory_items(["/uploads/images/adena.png"])

        self.assertTrue(vision.inventory_open)
        lines = [str(call.args[0]) for call in output.call_args_list]
        self.assertTrue(any(
            "开始检查物品栏打开状态" in line
            for line in lines
        ))
        self.assertTrue(any(
            "已识别到订单物品" in line
            for line in lines
        ))
        self.assertIn(
            (Ui.INVENTORY_BUTTON, Ui.INVENTORY_BUTTON_REGION, 0.84),
            vision.find_calls,
        )
        self.assertIn(
            (Ui.INVENTORY_OPEN, Ui.INVENTORY_OPEN_REGION, 0.82),
            vision.find_calls,
        )
        self.assertTrue(all(
            region == Ui.INVENTORY_CONTENT_REGION
            for _image, region, _threshold in vision.find_image_calls
        ))
        self.assertEqual((600, 15, 770, 360), Ui.INVENTORY_CONTENT_REGION)
        self.assertEqual((755, 290, 800, 370), Ui.INVENTORY_OPEN_REGION)
        self.assertEqual((630, 560, 730, 600), Ui.INVENTORY_BUTTON_REGION)

    def test_inventory_already_open_does_not_click_toggle(self):
        vision = _Vision(inventory_open=True)
        hardware = _Hardware(vision)
        navigator = LineageSessionNavigator(
            hardware,
            _Window(),
            vision,
            sleep=lambda _seconds: None,
        )

        with mock.patch("builtins.print") as output:
            navigator.ensure_inventory_open()

        self.assertEqual([], hardware.moves)
        self.assertTrue(any(
            "已检测到打开状态" in str(call.args[0])
            for call in output.call_args_list
        ))

    def test_inventory_refresh_closes_and_reopens_an_already_open_panel(self):
        vision = _Vision(inventory_open=True)
        hardware = _Hardware(vision)
        navigator = LineageSessionNavigator(
            hardware,
            _Window(),
            vision,
            sleep=lambda _seconds: None,
        )

        navigator.ensure_inventory_open(refresh=True)

        self.assertTrue(vision.inventory_open)
        self.assertEqual(1, vision.inventory_refreshes)
        self.assertEqual(2, len(hardware.moves))

    def test_inventory_recognition_tries_selected_image_when_unselected_image_errors(self):
        class FirstImageFailsVision(_Vision):
            def find_image(self, image_source, region, threshold=0.90):
                if image_source.endswith("/adena.png"):
                    self.find_image_calls.append((image_source, region, threshold))
                    raise NavigationError("未选中图片临时加载失败")
                return super().find_image(image_source, region, threshold)

        vision = FirstImageFailsVision(
            inventory_open=True,
            item_points={
                "/uploads/images/adena-selected.png": (680, 200),
            },
        )
        navigator = LineageSessionNavigator(
            _Hardware(vision),
            _Window(),
            vision,
            sleep=lambda _seconds: None,
        )

        navigator.ensure_inventory_items([
            "/uploads/images/adena.png",
            "/uploads/images/adena-selected.png",
        ])

        self.assertEqual(
            [
                (
                    "/uploads/images/adena.png",
                    Ui.INVENTORY_CONTENT_REGION,
                    0.90,
                ),
                (
                    "/uploads/images/adena-selected.png",
                    Ui.INVENTORY_CONTENT_REGION,
                    0.90,
                ),
            ],
            vision.find_image_calls,
        )

    def test_inventory_uses_fixed_toggle_coordinate_when_template_is_missing(self):
        vision = _Vision(
            inventory_open=False,
            inventory_button_visible=False,
        )
        hardware = _Hardware(vision)
        navigator = LineageSessionNavigator(
            hardware,
            _Window(),
            vision,
            sleep=lambda _seconds: None,
        )

        with mock.patch("builtins.print") as output:
            navigator.ensure_inventory_open()

        self.assertTrue(vision.inventory_open)
        self.assertLessEqual(
            abs(hardware.moves[0][0] - Ui.INVENTORY_BUTTON_FALLBACK[0]),
            3,
        )
        self.assertLessEqual(
            abs(hardware.moves[0][1] - Ui.INVENTORY_BUTTON_FALLBACK[1]),
            3,
        )
        self.assertTrue(any(
            "source=800x600 固定按钮坐标" in str(call.args[0])
            for call in output.call_args_list
        ))

    def test_menu_toggle_uses_bottom_right_region_and_two_state_threshold(self):
        vision = _Vision()
        navigator = LineageSessionNavigator(
            _Hardware(vision),
            _Window(),
            vision,
            sleep=lambda _seconds: None,
        )

        point = navigator._find_menu_button()

        self.assertEqual(_Vision.CENTERS[Ui.MENU_BUTTON], point)
        self.assertEqual(
            (Ui.MENU_BUTTON, Ui.MENU_BUTTON_REGION, 0.60),
            vision.find_calls[-1],
        )
        self.assertEqual((785, 565, 800, 600), Ui.MENU_BUTTON_REGION)
        self.assertEqual((788, 570, 800, 600), Ui.MENU_BUTTON_CLICK_REGION)
        self.assertEqual((755, 560, 795, 600), Ui.EXIT_PANEL_TRIGGER_REGION)

    def test_menu_click_randomization_stays_inside_confirmed_button_bounds(self):
        vision = _Vision()
        hardware = _Hardware(vision)
        navigator = LineageSessionNavigator(
            hardware,
            _Window(),
            vision,
            sleep=lambda _seconds: None,
        )

        navigator._open_exit_panel_and_relogin()

        menu_x, menu_y = hardware.moves[0]
        self.assertTrue(789 <= menu_x <= 798)
        self.assertTrue(571 <= menu_y <= 598)
        self.assertTrue(vision.menu_open)

    def test_menu_decision_logs_each_probe_and_final_branch(self):
        vision = _Vision()
        navigator = LineageSessionNavigator(
            _Hardware(vision),
            _Window(),
            vision,
            sleep=lambda _seconds: None,
        )

        with mock.patch("builtins.print") as output:
            navigator._open_exit_panel_and_relogin()

        lines = [str(call.args[0]) for call in output.call_args_list]
        self.assertTrue(any(
            "[菜单判断] Restart 操作面板按钮: 结果=未命中" in line
            for line in lines
        ))
        self.assertTrue(any(
            "[菜单判断] 紫色 Restart 面板触发按钮: 结果=未命中" in line
            for line in lines
        ))
        self.assertTrue(any(
            "[菜单判断] 右下角切换菜单按钮: 结果=命中" in line
            for line in lines
        ))
        self.assertTrue(any(
            "matched_region=X[790,798] Y[571,597] size=9x27" in line
            for line in lines
        ))
        self.assertTrue(any(
            "search_region=X[785,799] Y[565,599]" in line
            for line in lines
        ))
        self.assertTrue(any(
            "[菜单判断结论] 未识别到紫色触发按钮" in line
            for line in lines
        ))

    def test_open_menu_continues_from_exit_trigger_without_toggling_closed(self):
        vision = _Vision()
        vision.menu_open = True
        hardware = _Hardware(vision)
        navigator = LineageSessionNavigator(
            hardware,
            _Window(),
            vision,
            sleep=lambda _seconds: None,
        )

        navigator._open_exit_panel_and_relogin()

        self.assertEqual("character", vision.state)
        self.assertTrue(vision.exit_panel_open)
        self.assertLessEqual(
            abs(hardware.moves[0][0] - _Vision.CENTERS[Ui.EXIT_PANEL_TRIGGER][0]),
            3,
        )
        self.assertFalse(any(
            abs(x - _Vision.CENTERS[Ui.MENU_BUTTON][0]) <= 3
            and abs(y - _Vision.CENTERS[Ui.MENU_BUTTON][1]) <= 3
            for x, y in hardware.moves
        ))

    def test_character_selection_uses_fixed_slot_and_ok_not_character_appearance(self):
        vision = _Vision(state="character")
        vision.pixel = mock.Mock(side_effect=AssertionError(
            "角色外观或旧像素不应参与选择"
        ))
        hardware = _Hardware(vision)
        navigator = LineageSessionNavigator(
            hardware,
            _Window(),
            vision,
            sleep=lambda _seconds: None,
        )

        navigator._select_character_and_login()

        slot_center = (
            (Ui.CHARACTER_PICK_REGION[0] + Ui.CHARACTER_PICK_REGION[2]) // 2,
            (Ui.CHARACTER_PICK_REGION[1] + Ui.CHARACTER_PICK_REGION[3]) // 2,
        )
        self.assertLessEqual(abs(hardware.moves[0][0] - slot_center[0]), 12)
        self.assertLessEqual(abs(hardware.moves[0][1] - slot_center[1]), 20)
        self.assertTrue(vision.character_selected)
        self.assertEqual("game", vision.state)
        self.assertIn(
            (Ui.CHARACTER_LOGIN, Ui.CHARACTER_ACTION_REGION, 0.84),
            vision.find_calls,
        )
        self.assertEqual(
            [(
                Ui.CHARACTER_NAME_VALUE_REGION,
                Ui.CHARACTER_VALUE_BRIGHTNESS,
            )],
            vision.bright_pixel_calls,
        )
        vision.pixel.assert_not_called()
        self.assertEqual((640, 480, 780, 555), Ui.CHARACTER_ACTION_REGION)
        self.assertEqual((212, 367, 450, 383), Ui.CHARACTER_NAME_VALUE_REGION)

    def test_screen_step_wait_uses_business_delay_and_fixed_detection_attempts(self):
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
        self.assertEqual([(1.0, 4.0)], random_ranges)
        # 画面切换：固定 1 + 随机上限 4，前两次未就绪各等待 1 秒。
        self.assertAlmostEqual(7.0, sum(sleeps), places=5)
        self.assertTrue(any(
            f"第 3/{lineage_navigation.STEP_VERIFY_ATTEMPTS} 次 已就绪"
            in call.args[0]
            for call in output.call_args_list
        ))

    def test_server_connect_initial_wait_is_2_to_5_seconds_and_keeps_checks(self):
        sleeps = []
        random_ranges = []
        outcomes = iter([None, (642, 451)])
        navigator = LineageSessionNavigator(
            mock.Mock(),
            _Window(),
            mock.Mock(),
            sleep=sleeps.append,
            random_uniform=lambda low, high: (
                random_ranges.append((low, high)) or high
            ),
        )

        with mock.patch("builtins.print") as output:
            result = navigator.wait_for_step(
                "等待账号确认页",
                lambda: next(outcomes),
                profile="server_connect",
            )

        self.assertEqual((642, 451), result)
        self.assertEqual([(1.0, 4.0)], random_ranges)
        self.assertAlmostEqual(6.0, sum(sleeps), places=5)
        self.assertTrue(any(
            f"第 2/{lineage_navigation.STEP_VERIFY_ATTEMPTS} 次 已就绪"
            in call.args[0]
            for call in output.call_args_list
        ))

    def test_failed_step_only_reports_error_after_fixed_checks(self):
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
        self.assertEqual(lineage_navigation.STEP_VERIFY_ATTEMPTS, checks)
        self.assertTrue(any(
            f"连续 {lineage_navigation.STEP_VERIFY_ATTEMPTS} 次检测"
            in call.args[0]
            for call in output.call_args_list
        ))

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

        self.assertAlmostEqual(5.0, sum(screen_sleeps), places=5)
        self.assertAlmostEqual(1.4, sum(item_sleeps), places=5)
        self.assertGreater(sum(screen_sleeps), sum(item_sleeps) * 3)

    def test_buyer_ocr_at_90_or_above_auto_accepts_only_matching_name(self):
        self.assertEqual("accept", buyer_ocr_action("홍길동이", "홍길동", 90.0))
        self.assertEqual("review", buyer_ocr_action("홍길순", "홍길동", 99.0))
        self.assertEqual(
            "accept",
            buyer_ocr_action(
                "TT석사TT",
                "TT석사TT",
                84.0,
                verified=True,
            ),
        )

    def test_buyer_ocr_below_90_always_needs_human_review(self):
        self.assertEqual("review", buyer_ocr_action("홍길동", "홍길동", 89.9))
        self.assertEqual("review", buyer_ocr_action("", "홍길동", -1.0))

    def test_chat_text_is_not_read_as_buyer_without_trade_request_popup(self):
        executor = LineageClassicExecutor(object())
        vision = mock.Mock()
        vision.find.return_value = None
        vision.read_text_result.return_value = SimpleNamespace(
            text="[TURTLE] 6힘지",
            confidence=99.0,
        )
        navigator = SimpleNamespace(
            vision=vision,
            _raise_if_cancelled=mock.Mock(),
            sleep=mock.Mock(),
        )

        with mock.patch.object(
            lineage_navigation.time,
            "monotonic",
            side_effect=[0.0, 0.1, 1.1],
        ):
            observed = executor._wait_for_expected_buyer(
                navigator,
                "주문고객",
                timeout=1.0,
            )

        self.assertIsNone(observed)
        vision.find.assert_called_once_with(
            TradeUi.REQUEST_TEMPLATE,
            TradeUi.REQUEST_TEMPLATE_REGION,
            threshold=0.86,
        )
        vision.read_text_result.assert_not_called()

    def test_buyer_name_is_read_only_after_trade_request_popup_is_visible(self):
        executor = LineageClassicExecutor(object())
        vision = mock.Mock()
        vision.find.return_value = (415, 532)
        vision.read_player_name_result.return_value = SimpleNamespace(
            text="Buyer27",
            confidence=96.0,
        )
        navigator = SimpleNamespace(
            vision=vision,
            _raise_if_cancelled=mock.Mock(),
            sleep=mock.Mock(),
        )

        with mock.patch.object(
            lineage_navigation.time,
            "monotonic",
            side_effect=[0.0, 0.1, 0.2, 0.3],
        ):
            observed = executor._wait_for_expected_buyer(
                navigator,
                "Buyer27",
                timeout=1.0,
            )

        self.assertEqual("Buyer27", observed)
        self.assertEqual(3, vision.find.call_count)
        self.assertEqual(3, vision.read_player_name_result.call_count)
        vision.read_player_name_result.assert_called_with(
            TradeUi.CUSTOMER_NAME_REGION,
            "Buyer27",
        )
        self.assertEqual(
            [mock.call(0.35), mock.call(0.35)],
            navigator.sleep.call_args_list,
        )

    def test_human_rejection_clicks_no_and_confirms_request_disappeared(self):
        executor = LineageClassicExecutor(object())
        vision = mock.Mock()
        vision.find.return_value = None
        navigator = mock.Mock()
        navigator.vision = vision
        navigator.wait_for_step.side_effect = (
            lambda _name, predicate, **_kwargs: predicate()
        )

        with mock.patch("builtins.print"):
            executor._reject_buyer_request(navigator)

        navigator.click_region.assert_called_once_with(
            TradeUi.REQUEST_REJECT_REGION
        )
        vision.find.assert_called_once_with(
            TradeUi.REQUEST_TEMPLATE,
            TradeUi.REQUEST_TEMPLATE_REGION,
            threshold=0.86,
        )
        self.assertNotIn(
            "attempts",
            navigator.wait_for_step.call_args.kwargs,
        )
        self.assertEqual(30, lineage_navigation.STEP_VERIFY_ATTEMPTS)

    def test_human_rejection_retries_when_request_is_still_visible(self):
        executor = LineageClassicExecutor(object())
        navigator = mock.Mock()
        navigator.wait_for_step.side_effect = [False, False, True]

        with mock.patch("builtins.print"):
            executor._reject_buyer_request(navigator)

        self.assertEqual(3, navigator.click_region.call_count)

    def test_trade_fixed_action_regions_use_the_provided_centers(self):
        self.assertEqual((537, 551), region_center(TradeUi.REQUEST_ACCEPT_REGION))
        self.assertEqual((568, 551), region_center(TradeUi.REQUEST_REJECT_REGION))
        self.assertEqual((537, 551), region_center(TradeUi.FINAL_ACCEPT_REGION))
        self.assertEqual((568, 551), region_center(TradeUi.FINAL_REJECT_REGION))

    def test_trade_window_regions_separate_my_items_from_buyer_items(self):
        self.assertEqual((0, 0, 235, 360), TradeUi.TRADE_WINDOW_REGION)
        self.assertEqual((22, 38, 190, 166), TradeUi.MY_TRADE_REGION)
        self.assertEqual((45, 59), TradeUi.MY_TRADE_FIRST_ITEM)
        self.assertEqual(8, TradeUi.MY_TRADE_FIRST_ITEM_HOVER_RADIUS)
        self.assertEqual((50, 65, 162, 140), TradeUi.MY_TRADE_DROP_REGION)
        self.assertEqual((22, 203, 190, 330), TradeUi.BUYER_TRADE_REGION)
        self.assertEqual((120, 330, 225, 360), TradeUi.TRADE_ACTION_REGION)
        self.assertEqual((106, 102), region_center(TradeUi.MY_TRADE_REGION))
        self.assertEqual((106, 102), region_center(TradeUi.MY_TRADE_DROP_REGION))
        self.assertEqual(
            (50, 65),
            random_region_point(
                TradeUi.MY_TRADE_DROP_REGION,
                lambda low, _high: low,
            ),
        )
        self.assertEqual(
            (161, 139),
            random_region_point(
                TradeUi.MY_TRADE_DROP_REGION,
                lambda _low, high: high,
            ),
        )

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

    def test_final_trade_screenshot_hovers_first_item_before_capture(self):
        executor = LineageClassicExecutor(object())
        navigator = mock.Mock()
        events = []
        navigator.move.side_effect = lambda *_args, **_kwargs: events.append("move")
        navigator.wait_after_step.side_effect = (
            lambda *_args, **_kwargs: events.append("wait")
        )
        navigator.vision.capture_data_url.side_effect = (
            lambda _region: events.append("capture") or "data:image/png;base64,test"
        )

        screenshot = executor._capture_final_trade_screenshot(navigator)

        self.assertEqual("data:image/png;base64,test", screenshot)
        self.assertEqual(["move", "wait", "capture"], events)
        navigator.move.assert_called_once_with(
            TradeUi.MY_TRADE_FIRST_ITEM,
            radius_x=8,
            radius_y=8,
        )
        navigator.wait_after_step.assert_called_once_with(
            "悬停我方交易区第一个物品并等待数量显示",
            profile="recognition",
            fixed_wait=0.5,
        )
        navigator.vision.capture_data_url.assert_called_once_with(Ui.FULL_CLIENT)

    def test_accepts_buyer_before_locating_inventory_items(self):
        executor = LineageClassicExecutor(object())
        navigator = mock.Mock()
        navigator.wait_for_step.return_value = (150, 340)
        events = []
        navigator.click_region.side_effect = lambda region: events.append(
            ("click", region)
        )
        executor._wait_for_expected_buyer = mock.Mock(return_value="Buyer")

        def stop_after_item_lookup(_order, _navigator):
            events.append(("locate_items", None))
            raise NavigationError("停止测试")

        executor._build_transfers = mock.Mock(side_effect=stop_after_item_lookup)
        order = {**ORDER, "buyer_character": "Buyer"}

        with mock.patch(
            "game_executor.executor.lineage_classic.executor.build_navigator",
            return_value=navigator,
        ):
            with self.assertRaisesRegex(NavigationError, "停止测试"):
                executor._execute_sync(order)

        self.assertEqual(
            [
                ("click", TradeUi.REQUEST_ACCEPT_REGION),
                ("locate_items", None),
            ],
            events,
        )

    def test_trade_close_verification_uses_fixed_polling_and_3_stable_frames(self):
        executor = LineageClassicExecutor(object())
        navigator = mock.Mock()
        navigator.vision.find.return_value = None
        navigator._is_in_game.return_value = True
        wait_options = {}

        def verify_three_frames(_name, predicate, **options):
            wait_options.update(options)
            self.assertFalse(predicate())
            self.assertFalse(predicate())
            return predicate()

        navigator.wait_for_step.side_effect = verify_three_frames

        self.assertTrue(executor._wait_for_trade_closed(navigator, timeout=12))
        self.assertNotIn("attempts", wait_options)
        self.assertEqual(30, lineage_navigation.STEP_VERIFY_ATTEMPTS)
        self.assertEqual(0.5, wait_options["probe_interval"])

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

    def test_item_accepts_unselected_recognition_image_without_selected_image(self):
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

        transfers = executor._build_transfers(
            order,
            _instant_navigator(_Vision(
                inventory_open=True,
                item_points={"/images/red.png": (680, 200)},
            )),
        )

        self.assertEqual([((680, 200), 3)], [
            (transfer.source, transfer.quantity) for transfer in transfers
        ])

    def test_item_requires_at_least_one_recognition_image(self):
        executor = LineageClassicExecutor(object())
        order = {
            "asset_type": "item",
            "details": [{
                "item_id": 11,
                "item_name": "红水",
                "quantity": 3,
            }],
        }

        with self.assertRaisesRegex(NavigationError, "至少提供一张"):
            executor._build_transfers(
                order, _instant_navigator(_Vision(inventory_open=True))
            )

    def test_trade_timeout_uses_order_value_and_safe_bounds(self):
        self.assertEqual(600, trade_timeout_seconds({}))
        self.assertEqual(600, trade_timeout_seconds({"trade_timeout_seconds": 600}))
        self.assertEqual(30, trade_timeout_seconds({"trade_timeout_seconds": 1}))
        self.assertEqual(7200, trade_timeout_seconds({"trade_timeout_seconds": 99999}))

    def test_buyer_poll_schedule_changes_at_one_and_seven_minutes(self):
        self.assertEqual(("初始低频", 5.0), buyer_poll_schedule(0))
        self.assertEqual(("初始低频", 5.0), buyer_poll_schedule(59.9))
        self.assertEqual(("中段高频", 2.0), buyer_poll_schedule(60))
        self.assertEqual(("中段高频", 2.0), buyer_poll_schedule(419.9))
        self.assertEqual(("后段低频", 5.0), buyer_poll_schedule(420))
        self.assertEqual(("后段低频", 5.0), buyer_poll_schedule(600))

    def test_screen_capture_timeout_reports_error_instead_of_hanging(self):
        vision = object.__new__(TemplateVision)
        vision.window = _Window()
        release = threading.Event()
        started = threading.Event()

        def blocked_grab(**_kwargs):
            started.set()
            release.wait(1.0)
            return mock.Mock()

        try:
            with mock.patch.object(
                lineage_navigation,
                "ImageGrab",
                SimpleNamespace(grab=blocked_grab),
            ), mock.patch.object(
                lineage_navigation,
                "CAPTURE_TIMEOUT_SECONDS",
                0.01,
            ):
                with self.assertRaisesRegex(NavigationError, "截图超过"):
                    vision._capture(Ui.SERVER_REGION)
            self.assertTrue(started.is_set())
        finally:
            release.set()

    def test_all_navigation_templates_can_be_loaded_from_unicode_paths(self):
        try:
            vision = TemplateVision(_Window())
        except Exception as exc:
            self.skipTest(str(exc))
        templates = (
            Ui.INVENTORY_BUTTON,
            Ui.INVENTORY_OPEN,
            Ui.IN_GAME_ANCHOR,
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

    def test_missing_final_confirmation_reports_recognition_uncertainty(self):
        source = inspect.getsource(LineageClassicExecutor._execute_sync)

        self.assertIn("未识别到最终交易确认提示", source)
        self.assertNotIn("没有可继续操作的按钮", source)

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

        self.assertEqual([], vision.page_number_calls)
        self.assertEqual(1, vision.current_page)
        self.assertEqual(20, Ui.SERVER_SELECT_RADIUS_X)
        self.assertEqual(2, Ui.SERVER_SELECT_RADIUS_Y)
        self.assertLessEqual(
            abs(ORDER["region_select_x"] - hardware.moves[1][0]),
            Ui.SERVER_SELECT_RADIUS_X,
        )
        self.assertLessEqual(
            abs(ORDER["region_select_y"] - hardware.moves[1][1]),
            Ui.SERVER_SELECT_RADIUS_Y,
        )
        self.assertEqual(0, vision.find_text_calls)
        self.assertEqual("character", vision.state)

    def test_server_selection_switches_to_configured_page_before_server_coordinate(self):
        order = {**ORDER, "region_select_page": 2}
        vision = _Vision(state="server")
        hardware = _Hardware(vision)
        navigator = LineageSessionNavigator(
            hardware, _Window(), vision, sleep=lambda _seconds: None
        )

        navigator._select_server(TargetRegion.from_order(order))

        self.assertEqual([], vision.page_number_calls)
        self.assertEqual(2, vision.current_page)
        self.assertLessEqual(abs(364 - hardware.moves[0][0]), 2)
        self.assertLessEqual(abs(353 - hardware.moves[0][1]), 2)
        self.assertLessEqual(
            abs(ORDER["region_select_x"] - hardware.moves[1][0]),
            Ui.SERVER_SELECT_RADIUS_X,
        )
        self.assertLessEqual(
            abs(ORDER["region_select_y"] - hardware.moves[1][1]),
            Ui.SERVER_SELECT_RADIUS_Y,
        )
        self.assertIn(
            (
                Ui.ACCOUNT_CONFIRM_BUTTON,
                Ui.ACCOUNT_CONFIRM_REGION,
                0.84,
            ),
            vision.find_calls,
        )
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

        self.assertLessEqual(
            abs(470 - hardware.moves[1][0]),
            Ui.SERVER_SELECT_RADIUS_X,
        )
        self.assertLessEqual(
            abs(173 - hardware.moves[1][1]),
            Ui.SERVER_SELECT_RADIUS_Y,
        )
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

        self.assertEqual(1, len(hardware.moves))

    def test_server_selection_stops_when_non_visible_page_cannot_be_located(self):
        vision = _Vision(state="server", page_points={3: (320, 390)})
        hardware = _Hardware(vision)
        navigator = LineageSessionNavigator(
            hardware, _Window(), vision, sleep=lambda _seconds: None
        )

        with self.assertRaisesRegex(NavigationError, "第 7 页分页按钮"):
            navigator._select_server(TargetRegion.from_order({
                **ORDER,
                "region_select_page": 7,
            }))

        self.assertEqual(
            [7] * lineage_navigation.STEP_VERIFY_ATTEMPTS,
            vision.page_number_calls,
        )
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

    def test_paddle_ocr_reads_direct_text_recognition_result(self):
        text, confidence = paddle_ocr_text([{
            "res": {
                "rec_text": "TT",
                "rec_score": 0.981,
            }
        }])
        self.assertEqual("TT", text)
        self.assertAlmostEqual(98.1, confidence)

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

    def test_direct_text_recognition_uses_language_specific_cpu_model(self):
        calls = []

        class FakeTextRecognition:
            def __init__(self, **kwargs):
                calls.append(kwargs)

        with mock.patch.dict(
            sys.modules,
            {"paddleocr": type(
                "Module",
                (),
                {"TextRecognition": FakeTextRecognition},
            )},
        ):
            build_text_recognition_engine("english")
            build_text_recognition_engine("korean")

        self.assertEqual("en_PP-OCRv5_mobile_rec", calls[0]["model_name"])
        self.assertEqual("korean_PP-OCRv5_mobile_rec", calls[1]["model_name"])
        self.assertEqual("cpu", calls[0]["device"])
        self.assertFalse(calls[0]["enable_mkldnn"])

    def test_cached_same_region_skips_relogin_but_still_opens_inventory(self):
        vision = _Vision(current_text=ORDER["region_code"], inventory_open=False)
        window = _Window()
        cache = RegionSessionCache()
        hardware = _Hardware(vision)
        navigator = LineageSessionNavigator(
            hardware,
            window,
            vision,
            sleep=lambda _seconds: None,
            region_session_cache=cache,
        )

        first_target = navigator.ensure_target_region(ORDER)

        self.assertEqual(ORDER["region_id"], first_target.region_id)
        self.assertEqual(ORDER["region_id"], cache.snapshot().region_id)
        self.assertTrue(vision.menu_open)
        self.assertTrue(vision.exit_panel_open)
        self.assertTrue(vision.character_selected)

        vision.menu_open = False
        vision.exit_panel_open = False
        vision.server_selected = False
        vision.character_selected = False
        vision.inventory_open = True
        # 上一单拖拽物品后，第二单进入时同一商品仍可能保持选中高亮。
        vision.item_points = {
            "/uploads/images/adena-selected.png": (680, 200),
        }
        hardware.moves.clear()

        second_target = navigator.ensure_target_region(ORDER)

        self.assertEqual(ORDER["region_id"], second_target.region_id)
        self.assertFalse(vision.menu_open)
        self.assertFalse(vision.exit_panel_open)
        self.assertFalse(vision.server_selected)
        self.assertFalse(vision.character_selected)
        self.assertTrue(vision.inventory_open)
        self.assertEqual("game", vision.state)
        self.assertTrue(window.focused)
        self.assertTrue(window.validated)
        self.assertEqual(2, len(hardware.moves))
        self.assertIn(
            (
                "/uploads/images/adena-selected.png",
                Ui.INVENTORY_CONTENT_REGION,
                0.90,
            ),
            vision.find_image_calls,
        )
        self.assertFalse(any(
            abs(point[0] - ORDER["region_select_x"]) <= Ui.SERVER_SELECT_RADIUS_X
            and abs(point[1] - ORDER["region_select_y"]) <= Ui.SERVER_SELECT_RADIUS_Y
            for point in hardware.moves
        ))

    def test_changed_region_invalidates_cache_and_logs_in_again(self):
        vision = _Vision(current_text=ORDER["region_code"], inventory_open=False)
        cache = RegionSessionCache()
        navigator = LineageSessionNavigator(
            _Hardware(vision),
            _Window(),
            vision,
            sleep=lambda _seconds: None,
            region_session_cache=cache,
        )
        navigator.ensure_target_region(ORDER)

        vision.menu_open = False
        vision.exit_panel_open = False
        vision.server_selected = False
        vision.character_selected = False
        vision.inventory_open = False
        changed_order = {
            **ORDER,
            "region_id": 13,
            "region_name": "另一个大区",
            "region_code": "다른서버",
        }

        navigator.ensure_target_region(changed_order)

        self.assertTrue(vision.menu_open)
        self.assertTrue(vision.exit_panel_open)
        self.assertTrue(vision.server_selected)
        self.assertTrue(vision.character_selected)
        self.assertEqual(13, cache.snapshot().region_id)

    def test_region_cache_is_kept_when_inventory_recognition_fails_after_login(self):
        order = {
            **ORDER,
            "details": [{
                "item_id": 99,
                "item_name": "不存在的测试物品",
                "quantity": 1,
                "recognition_image_unselected_url": "/images/missing.png",
            }],
        }
        vision = _Vision(
            current_text=ORDER["region_code"],
            inventory_open=False,
            item_points={"/images/other.png": (680, 200)},
        )
        cache = RegionSessionCache()
        navigator = LineageSessionNavigator(
            _Hardware(vision),
            _Window(),
            vision,
            sleep=lambda _seconds: None,
            region_session_cache=cache,
        )

        with self.assertRaisesRegex(NavigationError, "未识别到订单物品"):
            navigator.ensure_target_region(order)

        self.assertEqual(ORDER["region_id"], cache.snapshot().region_id)

    def test_single_recognition_state_continues_after_inventory_is_opened(self):
        order = {
            **ORDER,
            "details": [{
                "item_id": 1,
                "item_name": "Adena",
                "quantity": 1,
                "recognition_image_unselected_url": "/uploads/images/adena.png",
            }],
        }
        vision = _Vision(current_text=ORDER["region_code"], inventory_open=False)
        navigator = LineageSessionNavigator(
            _Hardware(vision), _Window(), vision, sleep=lambda _seconds: None
        )

        navigator.ensure_target_region(order)

        self.assertTrue(vision.inventory_open)
        self.assertIn(
            (
                "/uploads/images/adena.png",
                Ui.INVENTORY_CONTENT_REGION,
                0.90,
            ),
            vision.find_image_calls,
        )

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
            if abs(point[0] - ORDER["region_select_x"]) <= Ui.SERVER_SELECT_RADIUS_X
            and abs(point[1] - ORDER["region_select_y"]) <= Ui.SERVER_SELECT_RADIUS_Y
        ]
        self.assertEqual(1, len(server_clicks))


if __name__ == "__main__":
    unittest.main()
