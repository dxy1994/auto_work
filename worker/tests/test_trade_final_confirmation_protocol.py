import unittest

from common.reporter import Reporter


class TradeFinalConfirmationProtocolTest(unittest.TestCase):

    def test_reporter_waits_for_final_confirmation_result(self):
        sent = []

        class Client:
            def send_threadsafe(self, message):
                sent.append(message)
                reporter.deliver_trade_final_confirmation_result(
                    message["request_id"],
                    {
                        "approved": False,
                        "reply_received": True,
                        "reply_text": "아니요",
                        "error": "买家回复不是韩文肯定答复",
                    },
                )

        reporter = Reporter(Client())
        result = reporter.request_trade_final_confirmation(
            "assignment-1",
            "/uploads/trade-screenshots/proof.png",
            timeout=0.1,
        )

        self.assertEqual("trade_final_confirmation", sent[0]["type"])
        self.assertEqual("assignment-1", sent[0]["assignment_id"])
        self.assertFalse(result["approved"])
        self.assertTrue(result["reply_received"])
        self.assertEqual("아니요", result["reply_text"])


if __name__ == "__main__":
    unittest.main()
