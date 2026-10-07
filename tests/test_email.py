"""Unit tests for email templates and services."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "aws-backend"))
from email_service.mock import MockEmailService
from template import format_email_report, format_subject, get_status_indicator


class TestEmail(unittest.TestCase):

    def setUp(self):
        self.bangalore_data = {
            "office_id": "bangalore",
            "office_name": "Bangalore",
            "timestamp": "2026-10-07T11:00:00+05:30",
            "status": "HEALTHY",
            "checks": {
                "internet": "UP",
                "gateway": "UP",
                "dns": "OK",
                "packet_loss": 0,
                "latency": 31,
                "download": 94,
                "upload": 21,
            },
            "classifications": {
                "internet": "HEALTHY",
                "gateway": "HEALTHY",
                "dns": "HEALTHY",
                "packet_loss": "HEALTHY",
                "latency": "HEALTHY",
                "download": "HEALTHY",
                "upload": "HEALTHY",
            },
        }
        self.mangalore_data = {
            "office_id": "mangalore",
            "office_name": "Mangalore",
            "timestamp": "2026-10-07T11:00:00+05:30",
            "status": "HEALTHY",
            "checks": {
                "internet": "UP",
                "gateway": "UP",
                "dns": "OK",
                "packet_loss": 1,
                "latency": 45,
                "download": 87,
                "upload": 19,
            },
            "classifications": {
                "internet": "HEALTHY",
                "gateway": "HEALTHY",
                "dns": "HEALTHY",
                "packet_loss": "HEALTHY",
                "latency": "HEALTHY",
                "download": "HEALTHY",
                "upload": "HEALTHY",
            },
        }

    def test_format_subject(self):
        subj = format_subject("2026-10-07T11:00:00+05:30")
        self.assertEqual(subj, "Office Network Health Report — 07 Oct 2026 11:00")

    def test_single_office_report(self):
        subject, html, text = format_email_report(
            [self.bangalore_data],
            "Bangalore is operating normally.",
            "No immediate action required.",
        )
        self.assertIn("Office Network Health Report", subject)
        self.assertIn("Internet", text)
        self.assertIn("94 Mbps", text)
        self.assertIn("No immediate action required.", text)
        self.assertIn("<table", html)
        self.assertIn("Bangalore", html)

    def test_multi_office_report(self):
        """PRD Section 21: Table with Bangalore and Mangalore columns."""
        subject, html, text = format_email_report(
            [self.bangalore_data, self.mangalore_data],
            "Bangalore and Mangalore operating normally.",
            "No immediate action required.",
        )
        self.assertIn("Bangalore", text)
        self.assertIn("Mangalore", text)
        self.assertIn("31 ms", text)
        self.assertIn("45 ms", text)
        self.assertIn(">Bangalore</th>", html)
        self.assertIn(">Mangalore</th>", html)

    def test_mock_email_service(self):
        mock_svc = MockEmailService()
        res = mock_svc.send_email(
            subject="Test Subject",
            html_content="<p>Test</p>",
            text_content="Test",
            recipients="admin@example.com",
        )
        self.assertTrue(res)
        self.assertEqual(len(mock_svc.sent_messages), 1)
        self.assertEqual(mock_svc.sent_messages[0]["subject"], "Test Subject")
        self.assertEqual(mock_svc.sent_messages[0]["to"], "admin@example.com")

    def test_smtp_multiple_recipients(self):
        from unittest.mock import MagicMock, patch
        from email_service.smtp import SmtpEmailService

        svc = SmtpEmailService(from_email="noreply@example.com")
        with patch("smtplib.SMTP") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value = mock_server

            # Test comma-separated string
            success = svc.send_email(
                subject="Test",
                html_content="<p>Hi</p>",
                text_content="Hi",
                recipients="user1@company.com, user2@company.com, user3@company.com",
            )
            self.assertTrue(success)
            args, _ = mock_server.sendmail.call_args
            self.assertEqual(args[1], ["user1@company.com", "user2@company.com", "user3@company.com"])

            # Test semicolon-separated string
            success = svc.send_email(
                subject="Test",
                html_content="<p>Hi</p>",
                text_content="Hi",
                recipients="user1@company.com; user2@company.com",
            )
            self.assertTrue(success)
            args, _ = mock_server.sendmail.call_args
            self.assertEqual(args[1], ["user1@company.com", "user2@company.com"])


if __name__ == "__main__":
    unittest.main()

