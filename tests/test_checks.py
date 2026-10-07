"""Unit tests for individual network health checks."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "office-monitor"))
from checks.dns import check_dns
from checks.gateway import check_gateway
from checks.internet import check_internet
from checks.latency import classify_latency, classify_packet_loss
from checks.ping_utils import parse_ping_output


class TestChecks(unittest.TestCase):

    def test_parse_windows_ping(self):
        sample = (
            "Pinging 8.8.8.8 with 32 bytes of data:\n"
            "Reply from 8.8.8.8: bytes=32 time=14ms TTL=117\n"
            "Reply from 8.8.8.8: bytes=32 time=15ms TTL=117\n\n"
            "Ping statistics for 8.8.8.8:\n"
            "    Packets: Sent = 4, Received = 4, Lost = 0 (0% loss),\n"
            "Approximate round trip times in milli-seconds:\n"
            "    Minimum = 14ms, Maximum = 18ms, Average = 16ms\n"
        )
        res = parse_ping_output(sample, count=4)
        self.assertEqual(res["sent"], 4)
        self.assertEqual(res["received"], 4)
        self.assertEqual(res["loss_percent"], 0.0)
        self.assertEqual(res["avg_ms"], 16.0)

    def test_parse_unix_ping(self):
        sample = (
            "PING 1.1.1.1 (1.1.1.1): 56 data bytes\n"
            "64 bytes from 1.1.1.1: icmp_seq=0 ttl=57 time=12.3 ms\n"
            "64 bytes from 1.1.1.1: icmp_seq=1 ttl=57 time=14.5 ms\n\n"
            "--- 1.1.1.1 ping statistics ---\n"
            "2 packets transmitted, 2 packets received, 0.0% packet loss\n"
            "round-trip min/avg/max/stddev = 12.300/13.400/14.500/1.100 ms\n"
        )
        res = parse_ping_output(sample, count=2)
        self.assertEqual(res["sent"], 2)
        self.assertEqual(res["received"], 2)
        self.assertEqual(res["loss_percent"], 0.0)
        self.assertEqual(res["avg_ms"], 13.4)

    def test_classify_packet_loss(self):
        self.assertEqual(classify_packet_loss(0.0), "HEALTHY")
        self.assertEqual(classify_packet_loss(2.0), "HEALTHY")
        self.assertEqual(classify_packet_loss(3.5), "WARNING")
        self.assertEqual(classify_packet_loss(15.0), "CRITICAL")

    def test_classify_latency(self):
        self.assertEqual(classify_latency(45.0), "HEALTHY")
        self.assertEqual(classify_latency(150.0), "WARNING")
        self.assertEqual(classify_latency(350.0), "CRITICAL")
        self.assertEqual(classify_latency(None), "CRITICAL")

    def test_check_dns_live(self):
        res = check_dns(targets=["google.com", "cloudflare.com"])
        self.assertEqual(res["status"], "OK")
        self.assertEqual(res["classification"], "HEALTHY")
        self.assertEqual(len(res["resolved"]), 2)

    def test_check_gateway_live(self):
        res = check_gateway()
        self.assertIn(res["status"], ("UP", "UNKNOWN"))
        if res["status"] == "UP":
            self.assertIsNotNone(res["address"])

    def test_check_internet_live(self):
        res = check_internet(dns_status="OK")
        self.assertIn(res["status"], ("UP", "DOWN", "PARTIALLY AVAILABLE"))


if __name__ == "__main__":
    unittest.main()
