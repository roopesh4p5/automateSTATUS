"""Local development HTTP server simulating API Gateway + AWS Lambda.

Allows local end-to-end testing of the complete flow:
Office Monitor -> POST /health -> Lambda Handler -> Grok -> Email
"""

import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import logging
import os
import sys

# Support running directly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lambda_function import lambda_handler

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
)
logger = logging.getLogger("LocalAPIGateway")


class HealthApiHandler(BaseHTTPRequestHandler):
    """HTTP handler mimicking AWS API Gateway REST proxy integration."""

    def do_POST(self):
        if self.path != "/health" and self.path != "/health/":
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": f"Path '{self.path}' not found. Use POST /health"}).encode("utf-8"))
            return

        # Read body
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else ""

        # Normalize headers
        headers_dict = {k.lower(): v for k, v in self.headers.items()}

        # Build mock API Gateway event
        event = {
            "httpMethod": "POST",
            "path": "/health",
            "headers": headers_dict,
            "body": body,
        }

        # Invoke Lambda Handler
        result = lambda_handler(event)

        status_code = result.get("statusCode", 200)
        resp_headers = result.get("headers", {"Content-Type": "application/json"})
        resp_body = result.get("body", "{}")

        self.send_response(status_code)
        for h_key, h_val in resp_headers.items():
            self.send_header(h_key, h_val)
        self.end_headers()
        self.wfile.write(resp_body.encode("utf-8"))

    def do_GET(self):
        if self.path == "/health" or self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "API Gateway emulator running. Send POST to /health"}).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        logger.info("%s - - [%s] %s", self.client_address[0], self.log_date_time_string(), format % args)


def run_server(host: str = "0.0.0.0", port: int = 8080):
    server = HTTPServer((host, port), HealthApiHandler)
    logger.info("Local API Gateway server running at http://%s:%d/health", host, port)
    logger.info("Ready to accept reports from office-monitor!")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Stopping local server.")
        server.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Local API Gateway + Lambda Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8080, help="Port (default 8080)")
    args = parser.parse_args()

    run_server(args.host, args.port)
