"""Unit tests for Grok service summarization and rule parsing."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "aws-backend"))
from grok_service import generate_rule_based_analysis, parse_grok_response


class TestGrok(unittest.TestCase):

    def test_rule_based_analysis_healthy(self):
        offices = [{
            "office_id": "bangalore",
            "office_name": "Bangalore",
            "status": "HEALTHY",
            "diagnosis": "All network health checks are operating normally.",
            "checks": {"internet": "UP", "gateway": "UP", "dns": "OK", "packet_loss": 0, "latency": 30},
        }]
        summary, action = generate_rule_based_analysis(offices)
        self.assertIn("Bangalore is operating normally", summary)
        self.assertEqual(action, "No immediate action required.")

    def test_rule_based_analysis_isp_down(self):
        offices = [{
            "office_id": "bangalore",
            "office_name": "Bangalore",
            "status": "CRITICAL",
            "diagnosis": "Likely ISP/WAN outage.",
            "checks": {"internet": "DOWN", "gateway": "UP", "dns": "FAILED", "packet_loss": 100},
        }]
        summary, action = generate_rule_based_analysis(offices)
        self.assertIn("CRITICAL", summary)
        self.assertIn("ISP", action)

    def test_parse_grok_response_standard(self):
        sample_grok_output = (
            "Summary:\n"
            "Bangalore internet is currently degraded. Latency is elevated at 320 ms and packet loss is 8%.\n\n"
            "Action Needed:\n"
            "Check the WAN/ISP connection and router logs. If packet loss persists across the next check, contact the ISP."
        )
        summary, action = parse_grok_response(sample_grok_output, [])
        self.assertIn("Bangalore internet is currently degraded", summary)
        self.assertIn("Check the WAN/ISP connection", action)


if __name__ == "__main__":
    unittest.main()
