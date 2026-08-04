import asyncio
import inspect
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch


WORKER_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKER_ROOT))

from monitor.monitoring.platforms import itembay as itembay_module  # noqa: E402
from monitor.monitoring.platforms.itembay import (  # noqa: E402
    ItembayMonitor,
    ItembayOrderWorker,
    ItembayPresaleChatWorker,
    ItembayRefreshWorker,
    ORDER_LIST_URL,
    _combine_order_row_payloads,
    _parse_order_row_payload,
    _parse_presale_inquiry_payload,
    _parse_refresh_action,
)
from monitor.orders.adapters import adapter_for  # noqa: E402


class _FakeSession:
    account_id = 3

    @staticmethod
    def is_login_page(_url):
        return False


def _active_order_payload(**overrides):
    payload = {
        "cells": [
            "S33558282308",
            "게임머니",
            "%아데나%\n리니지클래식 - 오렌\n베이톡",
            "330만",
            "349,800원",
            "상품전달완료",
            "취소 및 신고",
        ],
        "subject_lines": [
            "%아데나%",
            "리니지클래식 - 오렌",
            "베이톡",
        ],
        "title_link_text": "%아데나%",
        "attributes": [
            "fncSetGiveItem('96376891', 'S', '3', '0')",
            "fncCancel('96376891', '33558282308')",
        ],
        "data_tran_seq": "",
        "character_candidates": [{
            "text": "복사",
            "onclick": "fncCharacterNameCopy('테스트기사')",
            "data_character_name": "",
            "data_character": "",
        }],
        "has_delivery_action": True,
    }
    payload.update(overrides)
    return payload


class ItembayStructureTest(unittest.IsolatedAsyncioTestCase):
    def _order_worker(self):
        monitor = SimpleNamespace(
            get_order_cfg=lambda: {
                "refresh_interval": 3,
                "wait_timeout": 10000,
            },
        )
        worker = ItembayOrderWorker(_FakeSession(), None, monitor)
        page = SimpleNamespace(
            url=ORDER_LIST_URL,
            reload=AsyncMock(),
            goto=AsyncMock(),
            wait_for_selector=AsyncMock(),
            evaluate=AsyncMock(return_value=100.0),
            is_closed=MagicMock(return_value=False),
        )
        worker._page = page
        return worker, page

    def test_order_row_uses_transaction_id_and_visible_business_fields(self):
        order = _parse_order_row_payload(_active_order_payload())

        self.assertEqual("96376891", order["order_no"])
        self.assertEqual("S33558282308", order["item_seq"])
        self.assertEqual("리니지클래식", order["game_name"])
        self.assertEqual("오렌", order["server_id"])
        self.assertEqual("%아데나%", order["title"])
        self.assertEqual("330만", order["trade_amount"])
        self.assertEqual("테스트기사", order["character"])
        self.assertEqual("paid", order["trade_status"])
        self.assertEqual("paid", order["state"])

    def test_live_two_row_order_combines_buyer_character_href(self):
        primary = _active_order_payload(
            row_span=2,
            character_candidates=[],
            attributes=[
                "https://www.itembay.com/scripting/scriptProc?"
                "url=/item/transaction/transactionGiveTakeDetail?"
                "iTranSeq=96376891&vcDepth=0",
            ],
        )
        buyer_detail = {
            "cells": [
                "구매자 TEST BUYER [캐릭터명 : 테스트기사]",
                "IB코드 판매자 1234 | 구매자 5678",
                "베이톡",
            ],
            "attributes": [
                "javascript:fncCharacterNameCopy('테스트기사');",
                "javascript:;",
            ],
            "character_candidates": [{
                "text": "",
                "href": "javascript:fncCharacterNameCopy('테스트기사');",
                "onclick": "",
                "data_character_name": "",
                "data_character": "",
            }],
            "row_span": 1,
            "is_buyer_detail": True,
        }

        payloads = _combine_order_row_payloads(
            [primary, buyer_detail])

        self.assertEqual(1, len(payloads))
        order = _parse_order_row_payload(payloads[0])
        self.assertEqual("96376891", order["order_no"])
        self.assertEqual("테스트기사", order["character"])

    def test_order_row_falls_back_to_item_number_without_transaction_id(self):
        payload = _active_order_payload(
            attributes=[],
            data_tran_seq="",
            has_delivery_action=False,
        )

        order = _parse_order_row_payload(payload)

        self.assertEqual("S33558282308", order["order_no"])
        self.assertEqual("trading", order["trade_status"])

    def test_empty_order_row_is_not_an_extraction_failure(self):
        self.assertIsNone(_parse_order_row_payload({
            "cells": ["** 상품전달완료 하실 상품이 없습니다. **"],
        }))

    def test_refresh_action_reads_status_and_remaining_count(self):
        action = _parse_refresh_action(
            "fncSetReRegistTop('33572289620', '3786', "
            "'12727', '0', '1', '100');return false;"
        )

        self.assertEqual("33572289620", action["item_seq"])
        self.assertEqual(0, action["sell_status"])
        self.assertEqual(100, action["remaining"])

    async def test_normalized_order_uses_row_data_without_fake_buyer(self):
        monitor = object.__new__(ItembayMonitor)
        monitor.account_id = 3
        order = _parse_order_row_payload(_active_order_payload())

        normalized = await monitor._build_normalized_order(None, order)

        self.assertEqual("itembay", normalized.platform)
        self.assertEqual("96376891", normalized.source_order_no)
        self.assertEqual("오렌", normalized.region_external_key)
        self.assertEqual("테스트기사", normalized.buyer_character)
        self.assertEqual(3300000, normalized.quantity)
        self.assertEqual("리니지클래식", normalized.game_name)

    async def test_missing_character_stops_reporting(self):
        monitor = object.__new__(ItembayMonitor)
        monitor.account_id = 3
        payload = _active_order_payload(character_candidates=[])
        order = _parse_order_row_payload(payload)

        normalized = await monitor._build_normalized_order(None, order)

        self.assertIsNone(normalized)

    def test_itembay_adapter_accepts_delivered_trading_state(self):
        normalized = adapter_for("itembay").normalize({
            "item_order_no": "96376891",
            "server_id": "오렌",
            "title": "%아데나%",
            "trade_amount": "330만",
            "character": "테스트기사",
            "trade_status": "trading",
            "item_type": "게임머니",
            "game_name": "리니지클래식",
        })

        self.assertIsNotNone(normalized)
        self.assertEqual("trading", normalized.platform_status)

    async def test_order_worker_navigates_to_direct_ssl_order_document(self):
        worker, page = self._order_worker()
        page.url = "about:blank"

        ready = await worker._ensure_order_page_ready(10000)

        self.assertTrue(ready)
        page.goto.assert_awaited_once_with(
            ORDER_LIST_URL,
            wait_until="commit",
            timeout=15000,
        )
        page.wait_for_selector.assert_awaited_once()

    async def test_reload_timeout_accepts_new_ready_document(self):
        worker, page = self._order_worker()
        page.reload.side_effect = TimeoutError("commit timeout")
        page.evaluate.side_effect = [100.0, 200.0]

        await worker._reload_order_page(10000)

        page.goto.assert_not_awaited()
        page.wait_for_selector.assert_awaited_once()

    async def test_reload_without_new_document_performs_one_goto(self):
        worker, page = self._order_worker()
        page.reload.side_effect = TimeoutError("commit timeout")
        page.evaluate.return_value = 100.0

        with patch.object(itembay_module, "COMMIT_GRACE_SECONDS", 0.0):
            await worker._reload_order_page(10000)

        page.goto.assert_awaited_once()
        self.assertEqual(ORDER_LIST_URL, page.goto.await_args.args[0])

    def test_monitor_uses_independent_order_refresh_and_presale_workers(self):
        monitor = object.__new__(ItembayMonitor)
        monitor._session = _FakeSession()
        monitor.stop_event = None

        workers = monitor._get_workers()

        self.assertEqual(3, len(workers))
        self.assertIsInstance(workers[0], ItembayOrderWorker)
        self.assertIsInstance(workers[1], ItembayRefreshWorker)
        self.assertIsInstance(workers[2], ItembayPresaleChatWorker)

    def test_presale_payload_requires_a_positive_unread_count(self):
        self.assertIsNone(_parse_presale_inquiry_payload({
            "unread_text": "안 읽은 수",
            "talk_seq": "119633",
        }))
        self.assertEqual({
            "talk_seq": "119633",
            "item_seq": "33579710017",
            "game_server": "리니지클래식 > 군터",
            "last_time": "14:55",
            "unread_count": 12,
        }, _parse_presale_inquiry_payload({
            "unread_text": "안 읽은 수 12",
            "talk_seq": "119633",
            "item_seq": "33579710017",
            "game_server": "리니지클래식 > 군터",
            "last_time": "14:55",
        }))

    async def test_same_unread_presale_inquiry_repeats_until_cleared(self):
        monitor = SimpleNamespace(get_order_cfg=lambda: {})
        worker = ItembayPresaleChatWorker(
            _FakeSession(), None, monitor)
        inquiry = [{"unread_count": 1}]

        with patch.object(
                itembay_module,
                "play_alert_audio_async",
                new=AsyncMock(return_value=True)) as alert:
            self.assertTrue(await worker._announce_if_due(
                inquiry, now=100.0))
            self.assertFalse(await worker._announce_if_due(
                inquiry, now=101.0))
            self.assertTrue(await worker._announce_if_due(
                inquiry, now=121.0))
            self.assertFalse(await worker._announce_if_due(
                [], now=122.0))
            self.assertTrue(await worker._announce_if_due(
                inquiry, now=123.0))

        self.assertEqual(3, alert.await_count)

    def test_refresh_flow_matches_live_ajax_page_contract(self):
        source = inspect.getsource(ItembayRefreshWorker._do_refresh)

        self.assertIn("REFRESH_BUTTON_SELECTOR", source)
        self.assertIn("_parse_refresh_action", source)
        self.assertNotIn("query_selector", source)
        self.assertNotIn("imgSubmitButton", source)


if __name__ == "__main__":
    unittest.main()
