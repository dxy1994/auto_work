import unittest

from common.protocol import platform_login_verification_msg
from common.reporter import Reporter


class LoginVerificationProtocolTest(unittest.TestCase):

    def test_reporter_sends_account_scoped_verification_state(self):
        sent = []

        class Client:
            def send_threadsafe(self, message):
                sent.append(message)

        reporter = Reporter(Client())
        reporter.report_login_verification(
            7,
            "barotem",
            "required",
            "Google 验证码需要人工完成",
        )

        self.assertEqual(
            platform_login_verification_msg(
                account_id=7,
                platform="barotem",
                status="required",
                reason="Google 验证码需要人工完成",
            ),
            sent[0],
        )


if __name__ == "__main__":
    unittest.main()
