import os
import unittest
from unittest.mock import patch

import app


class AppTests(unittest.TestCase):
    def setUp(self):
        app.RATE_BUCKETS.clear()

    def test_normalize_phone_accepts_e164(self):
        self.assertEqual(app.normalize_phone("+1 555 123 4567"), "+15551234567")

    def test_normalize_phone_adds_default_country(self):
        self.assertEqual(app.normalize_phone("9876543210", "+91"), "+919876543210")

    def test_validate_payload_requires_consent(self):
        config = app.Config.from_env()
        with self.assertRaises(app.ValidationError):
            app.validate_send_payload(
                {"phone": "+15551234567", "channels": ["sms"], "consent": False},
                config,
            )

    def test_validate_payload_requires_channel(self):
        config = app.Config.from_env()
        with self.assertRaises(app.ValidationError):
            app.validate_send_payload(
                {"phone": "+15551234567", "channels": [], "consent": True},
                config,
            )

    def test_live_mode_requires_allow_list(self):
        with patch.dict(os.environ, {"APP_DRY_RUN": "false"}, clear=False):
            config = app.Config.from_env()
            with self.assertRaises(app.ValidationError):
                app.validate_send_payload(
                    {"phone": "+15551234567", "channels": ["sms"], "consent": True},
                    config,
                )

    def test_dry_run_does_not_require_provider_credentials(self):
        with patch.dict(os.environ, {"APP_DRY_RUN": "true"}, clear=False):
            response = app.handle_send(
                {
                    "phone": "+15551234567",
                    "channels": ["sms", "whatsapp", "call"],
                    "message": "Hello",
                    "consent": True,
                },
                "127.0.0.1",
            )
            self.assertTrue(response["ok"])
            self.assertTrue(response["dryRun"])
            self.assertEqual(
                [item["status"] for item in response["results"]],
                ["dry_run", "dry_run", "dry_run"],
            )

    def test_rate_limit_blocks_excess_requests(self):
        with patch.dict(
            os.environ,
            {
                "APP_DRY_RUN": "true",
                "APP_RATE_WINDOW_SECONDS": "3600",
                "APP_RATE_LIMIT_MAX": "1",
            },
            clear=False,
        ):
            payload = {
                "phone": "+15551234567",
                "channels": ["sms"],
                "message": "Hello",
                "consent": True,
            }
            app.handle_send(payload, "127.0.0.1")
            with self.assertRaises(app.RateLimitError):
                app.handle_send(payload, "127.0.0.1")


if __name__ == "__main__":
    unittest.main()
