"""End-to-end integration test runner.

Launches the local API Gateway emulator, runs the office monitor,
verifies authentication, payload transmission, Grok processing, and email generation.
"""

from http.server import HTTPServer
import json
import logging
import os
import subprocess
import sys
import threading
import time

# Ensure project paths are in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "aws-backend"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "office-monitor"))

from local_server import HealthApiHandler
from lambda_function import lambda_handler

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger("E2ETest")

TEST_PORT = 8999


def start_test_server():
    """Start local server in daemon thread."""
    server = HTTPServer(("127.0.0.1", TEST_PORT), HealthApiHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def test_full_flow():
    logger.info("=== Starting E2E Flow Test ===")

    # Configure environment for test
    os.environ["BANGALORE_API_KEY"] = "test-bangalore-secret"
    os.environ["MANGALORE_API_KEY"] = "test-mangalore-secret"
    os.environ["EMAIL_PROVIDER"] = "mock"
    os.environ["TO_EMAIL"] = "network-admin@company.com"

    server = start_test_server()
    logger.info("Test API Gateway running on port %d", TEST_PORT)
    time.sleep(0.5)

    # 1. Test Single Office Live Run (Bangalore)
    logger.info("\n--- Running Bangalore Office Monitor against Local Backend ---")
    monitor_cmd = [
        sys.executable,
        os.path.join(PROJECT_ROOT, "office-monitor", "monitor.py"),
        "--quick",  # Skip slow speed test for fast e2e validation
    ]
    env = os.environ.copy()
    env["AWS_ENDPOINT"] = f"http://127.0.0.1:{TEST_PORT}/health"
    env["API_KEY"] = "test-bangalore-secret"
    env["OFFICE_ID"] = "bangalore"
    env["OFFICE_NAME"] = "Bangalore"

    res = subprocess.run(monitor_cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print(res.stdout)
    assert res.returncode == 0, f"Monitor process failed with code {res.returncode}"
    assert "Report delivered successfully to AWS!" in res.stdout, "Delivery confirmation missing from stdout"
    logger.info("PASS: Bangalore Office Monitor completed and transmitted successfully!")

    # 2. Test Multi-Office Aggregated Report (Bangalore + Mangalore)
    logger.info("\n--- Testing Multi-Office Aggregation (Bangalore + Mangalore) ---")
    multi_office_payload = {
        "headers": {"x-api-key": "test-bangalore-secret"},
        "body": json.dumps({
            "offices": [
                {
                    "office_id": "bangalore",
                    "office_name": "Bangalore",
                    "timestamp": "2026-10-07T11:00:00+05:30",
                    "status": "HEALTHY",
                    "diagnosis": "All network health checks are operating normally.",
                    "checks": {
                        "internet": "UP",
                        "gateway": "UP",
                        "dns": "OK",
                        "packet_loss": 0.0,
                        "latency": 28.5,
                        "download": 98.4,
                        "upload": 22.1,
                    },
                },
                {
                    "office_id": "mangalore",
                    "office_name": "Mangalore",
                    "timestamp": "2026-10-07T11:00:00+05:30",
                    "status": "WARNING",
                    "diagnosis": "Office network operating with warnings: elevated latency at 215ms.",
                    "checks": {
                        "internet": "UP",
                        "gateway": "UP",
                        "dns": "OK",
                        "packet_loss": 3.0,
                        "latency": 215.0,
                        "download": 45.0,
                        "upload": 12.0,
                    },
                },
            ]
        }),
    }
    lambda_res = lambda_handler(multi_office_payload)
    assert lambda_res["statusCode"] == 200, f"Expected 200 but got {lambda_res['statusCode']}"
    resp_data = json.loads(lambda_res["body"])
    assert resp_data["status"] == "success"
    assert resp_data["offices_processed"] == 2
    logger.info("Multi-office Lambda response: %s", json.dumps(resp_data, indent=2))
    logger.info("PASS: Multi-office aggregation processed 2 offices successfully!")

    # 3. Test Unauthorized Access
    logger.info("\n--- Testing Authentication Rejection for Invalid API Key ---")
    unauth_payload = {
        "headers": {"x-api-key": "wrong-secret-key"},
        "body": json.dumps({"office_id": "bangalore", "checks": {}}),
    }
    unauth_res = lambda_handler(unauth_payload)
    assert unauth_res["statusCode"] == 401, f"Expected 401 Unauthorized but got {unauth_res['statusCode']}"
    logger.info("PASS: Unauthorized request properly rejected with 401!")

    # 4. Test Simulated Outage Diagnosis (Gateway DOWN + Internet DOWN)
    logger.info("\n--- Testing Router Failure Scenario (Gateway DOWN + Internet DOWN) ---")
    router_outage_payload = {
        "headers": {"x-api-key": "test-bangalore-secret"},
        "body": json.dumps({
            "office_id": "bangalore",
            "office_name": "Bangalore",
            "timestamp": "2026-10-07T11:00:00+05:30",
            "status": "CRITICAL",
            "diagnosis": "Likely local network/router problem. Local default gateway is unreachable.",
            "checks": {
                "internet": "DOWN",
                "gateway": "DOWN",
                "dns": "FAILED",
                "packet_loss": 100.0,
                "latency": None,
                "download": None,
                "upload": None,
            },
        }),
    }
    outage_res = lambda_handler(router_outage_payload)
    assert outage_res["statusCode"] == 200
    outage_data = json.loads(outage_res["body"])
    assert "router" in outage_data["action_needed"].lower() or "local" in outage_data["action_needed"].lower()
    logger.info("Outage diagnosis action: %s", outage_data["action_needed"])
    logger.info("PASS: Local router failure diagnosis correctly triggered local router recovery actions!")

    server.shutdown()
    logger.info("\n========================================================")
    logger.info("  ALL E2E INTEGRATION TESTS PASSED SUCCESSFULLY!       ")
    logger.info("========================================================")


if __name__ == "__main__":
    test_full_flow()
