"""Unit tests for technical state classification logic."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "office-monitor"))
from utils.classifier import evaluate_technical_state


class TestClassifier(unittest.TestCase):

    def setUp(self):
        self.healthy_gw = {"status": "UP", "classification": "HEALTHY", "address": "192.168.1.1"}
        self.down_gw = {"status": "DOWN", "classification": "CRITICAL", "address": "192.168.1.1"}
        self.healthy_dns = {"status": "OK", "classification": "HEALTHY"}
        self.failed_dns = {"status": "FAILED", "classification": "CRITICAL"}
        self.healthy_inet = {"status": "UP", "classification": "HEALTHY"}
        self.down_inet = {"status": "DOWN", "classification": "CRITICAL"}
        self.partial_inet = {"status": "PARTIALLY AVAILABLE", "classification": "WARNING"}
        self.healthy_lat_loss = {
            "packet_loss_percent": 0.0,
            "packet_loss_classification": "HEALTHY",
            "latency_ms": 25.0,
            "latency_classification": "HEALTHY",
        }
        self.healthy_speed = {
            "download_mbps": 90.0,
            "download_classification": "HEALTHY",
            "upload_mbps": 20.0,
            "upload_classification": "HEALTHY",
        }

    def test_all_healthy(self):
        status, diag, classes = evaluate_technical_state(
            self.healthy_inet, self.healthy_gw, self.healthy_dns, self.healthy_lat_loss, self.healthy_speed
        )
        self.assertEqual(status, "HEALTHY")
        self.assertIn("operating normally", diag)
        self.assertEqual(classes["internet"], "HEALTHY")
        self.assertEqual(classes["gateway"], "HEALTHY")

    def test_router_local_down(self):
        """PRD Section 13: Gateway DOWN + Internet DOWN -> Local network/router problem."""
        status, diag, classes = evaluate_technical_state(
            self.down_inet, self.down_gw, self.failed_dns, self.healthy_lat_loss, self.healthy_speed
        )
        self.assertEqual(status, "CRITICAL")
        self.assertIn("local network/router", diag.lower())

    def test_isp_wan_down(self):
        """PRD Section 13: Gateway UP + Internet DOWN -> ISP/WAN problem."""
        status, diag, classes = evaluate_technical_state(
            self.down_inet, self.healthy_gw, self.failed_dns, self.healthy_lat_loss, self.healthy_speed
        )
        self.assertEqual(status, "CRITICAL")
        self.assertIn("isp/wan", diag.lower())

    def test_dns_failure_ip_functional(self):
        """PRD Section 7: DNS failed while direct IP works -> PARTIALLY AVAILABLE."""
        status, diag, classes = evaluate_technical_state(
            self.partial_inet, self.healthy_gw, self.failed_dns, self.healthy_lat_loss, self.healthy_speed
        )
        self.assertIn(status, ("WARNING", "CRITICAL"))
        self.assertIn("dns", diag.lower())

    def test_packet_loss_warning(self):
        degraded_loss = {
            "packet_loss_percent": 6.5,
            "packet_loss_classification": "WARNING",
            "latency_ms": 40.0,
            "latency_classification": "HEALTHY",
        }
        status, diag, classes = evaluate_technical_state(
            self.healthy_inet, self.healthy_gw, self.healthy_dns, degraded_loss, self.healthy_speed
        )
        self.assertEqual(status, "WARNING")
        self.assertIn("packet loss", diag.lower())

    def test_high_latency_critical(self):
        critical_lat = {
            "packet_loss_percent": 1.0,
            "packet_loss_classification": "HEALTHY",
            "latency_ms": 350.0,
            "latency_classification": "CRITICAL",
        }
        status, diag, classes = evaluate_technical_state(
            self.healthy_inet, self.healthy_gw, self.healthy_dns, critical_lat, self.healthy_speed
        )
        self.assertEqual(status, "CRITICAL")
        self.assertIn("severe network degradation", diag.lower())


if __name__ == "__main__":
    unittest.main()
