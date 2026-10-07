"""Unit tests for AWS Lambda Handler."""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "aws-backend"))
from lambda_function import lambda_handler, validate_api_key


class TestLambdaHandler(unittest.TestCase):

    def setUp(self):
        os.environ["BANGALORE_API_KEY"] = "secret-blr"
        os.environ["MANGALORE_API_KEY"] = "secret-mng"
        os.environ["EMAIL_PROVIDER"] = "mock"

    def test_api_key_validation(self):
        self.assertTrue(validate_api_key({"x-api-key": "secret-blr"}, "bangalore"))
        self.assertTrue(validate_api_key({"authorization": "Bearer secret-blr"}, "bangalore"))
        self.assertFalse(validate_api_key({"x-api-key": "wrong"}, "bangalore"))
        self.assertFalse(validate_api_key({}, "bangalore"))

    def test_invalid_json_handling(self):
        event = {
            "headers": {"x-api-key": "secret-blr"},
            "body": "this is not valid json",
        }
        resp = lambda_handler(event)
        self.assertEqual(resp["statusCode"], 400)

    def test_missing_payload(self):
        event = {
            "headers": {"x-api-key": "secret-blr"},
            "body": "",
        }
        resp = lambda_handler(event)
        self.assertEqual(resp["statusCode"], 400)

    def test_unauthorized_rejection(self):
        event = {
            "headers": {"x-api-key": "bad-key"},
            "body": json.dumps({"office_id": "bangalore", "checks": {}}),
        }
        resp = lambda_handler(event)
        self.assertEqual(resp["statusCode"], 401)

    def test_successful_execution(self):
        event = {
            "headers": {"x-api-key": "secret-blr"},
            "body": json.dumps({
                "office_id": "bangalore",
                "office_name": "Bangalore",
                "timestamp": "2026-10-07T11:00:00+05:30",
                "status": "HEALTHY",
                "checks": {
                    "internet": "UP",
                    "gateway": "UP",
                    "dns": "OK",
                    "packet_loss": 0,
                    "latency": 25,
                    "download": 95,
                    "upload": 22,
                },
            }),
        }
        resp = lambda_handler(event)
        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertEqual(body["status"], "success")
        self.assertTrue(body["email_dispatched"])


if __name__ == "__main__":
    unittest.main()
