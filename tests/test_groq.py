"""Unit tests for Groq service summarization and rule parsing."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "aws-backend"))
from groq_service import generate_rule_based_analysis, parse_groq_response, summarize_with_groq


class TestGroq(unittest.TestCase):

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

    def test_parse_groq_response_standard(self):
        sample_groq_output = (
            "Summary:\n"
            "Bangalore internet is currently degraded. Latency is elevated at 320 ms and packet loss is 8%.\n\n"
            "Action Needed:\n"
            "Check the WAN/ISP connection and router logs. If packet loss persists across the next check, contact the ISP."
        )
        summary, action = parse_groq_response(sample_groq_output, [])
        self.assertIn("Bangalore internet is currently degraded", summary)
        self.assertIn("Check the WAN/ISP connection", action)

    def test_summarize_fallback_when_no_api_key(self):
        os.environ.pop("GROQ_API_KEY", None)
        os.environ.pop("GROK_API_KEY", None)
        offices = [{
            "office_id": "bangalore",
            "office_name": "Bangalore",
            "status": "HEALTHY",
            "diagnosis": "All network health checks are operating normally.",
            "checks": {"internet": "UP", "gateway": "UP", "dns": "OK", "packet_loss": 0, "latency": 20},
        }]
        summary, action = summarize_with_groq(offices)
        self.assertIn("Bangalore is operating normally", summary)
        self.assertEqual(action, "No immediate action required.")


if __name__ == "__main__":
    unittest.main()
