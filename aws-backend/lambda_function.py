"""AWS Lambda Handler for Office Network Health Monitoring (PRD Section 16-22)."""

import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

# Support running directly or inside Lambda
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from email_service import get_email_service
from grok_service import summarize_with_grok
from template import format_email_report

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
)
logger = logging.getLogger("HealthLambda")


def validate_api_key(headers: Dict[str, str], office_id: str) -> bool:
    """Validate office API key against configured secrets (PRD Section 18).

    Supports:
    - Office-specific env vars: e.g. BANGALORE_API_KEY, MANGALORE_API_KEY
    - Generic API_KEY env var
    - JSON mapping in OFFICE_API_KEYS env var
    """
    # Extract candidate keys from standard headers
    incoming_key = None
    for h_name in ("x-api-key", "X-API-Key", "authorization", "Authorization"):
        if h_name in headers:
            val = headers[h_name]
            if val.lower().startswith("bearer "):
                incoming_key = val[7:].strip()
            else:
                incoming_key = val.strip()
            break

    if not incoming_key:
        return False

    # Check office-specific key, e.g. BANGALORE_API_KEY
    clean_id = office_id.upper().replace("-", "_")
    specific_secret = os.environ.get(f"{clean_id}_API_KEY")
    if specific_secret and incoming_key == specific_secret:
        return True

    # Check generic API_KEY
    generic_secret = os.environ.get("API_KEY")
    if generic_secret and incoming_key == generic_secret:
        return True

    # Check OFFICE_API_KEYS JSON map e.g. '{"bangalore": "key1", "mangalore": "key2"}'
    office_keys_json = os.environ.get("OFFICE_API_KEYS")
    if office_keys_json:
        try:
            mapping = json.loads(office_keys_json)
            if mapping.get(office_id.lower()) == incoming_key:
                return True
        except Exception:
            pass

    # If no secrets are configured in environment at all, allow for initial MVP local development
    if not specific_secret and not generic_secret and not office_keys_json:
        logger.warning("No API keys configured in environment; allowing request for local development.")
        return True

    return False


def normalize_payload(body_data: Any) -> List[Dict[str, Any]]:
    """Normalize incoming payload into a list of standardized office check records."""
    if isinstance(body_data, list):
        return body_data
    elif isinstance(body_data, dict):
        if "offices" in body_data and isinstance(body_data["offices"], list):
            return body_data["offices"]
        else:
            return [body_data]
    return []


def lambda_handler(event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    """Main AWS Lambda entry point."""
    logger.info("Received event: %s", json.dumps(event) if isinstance(event, dict) else str(event))

    headers = event.get("headers", {}) or {}
    # Parse body
    raw_body = event.get("body")
    if raw_body is None and ("office_id" in event or "checks" in event or "offices" in event):
        body_data = event
    elif isinstance(raw_body, str):
        try:
            body_data = json.loads(raw_body)
        except Exception as e:
            logger.error("Invalid JSON body: %s", e)
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Invalid JSON format"}),
            }
    elif isinstance(raw_body, (dict, list)):
        body_data = raw_body
    else:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Empty or missing request payload"}),
        }

    offices = normalize_payload(body_data)
    if not offices:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "No office network data provided"}),
        }

    # Authenticate (PRD Section 18)
    first_office_id = offices[0].get("office_id", "unknown")
    if not validate_api_key(headers, first_office_id):
        logger.warning("Unauthorized access attempt for office: %s", first_office_id)
        return {
            "statusCode": 401,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Unauthorized: Invalid or missing API key"}),
        }

    logger.info("Processing health data for %d office(s): %s", len(offices), [o.get("office_id") for o in offices])

    # 1. Summarize and recommend actions with Grok (PRD Section 14 & 15)
    summary, action_needed = summarize_with_grok(offices)
    logger.info("Grok Summary: %s", summary)
    logger.info("Grok Action Needed: %s", action_needed)

    # 2. Format Email Report (PRD Section 21 & 22)
    subject, html_content, text_content = format_email_report(offices, summary, action_needed)

    # 3. Deliver Email (PRD Section 20)
    recipients = os.environ.get("REPORT_RECIPIENTS", os.environ.get("TO_EMAIL", "admin@company.com"))
    email_service = get_email_service()
    email_sent = email_service.send_email(
        subject=subject,
        html_content=html_content,
        text_content=text_content,
        recipients=recipients,
    )

    # 4. Return success response (PRD Section 19: discard data, no database storage)
    response_payload = {
        "status": "success",
        "offices_processed": len(offices),
        "overall_office_statuses": {o.get("office_id"): o.get("status", "HEALTHY") for o in offices},
        "summary": summary,
        "action_needed": action_needed,
        "email_dispatched": email_sent,
    }

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(response_payload),
    }


if __name__ == "__main__":
    # Test runner for local invocation
    test_event = {
        "headers": {"x-api-key": "test-key"},
        "body": json.dumps({
            "office_id": "bangalore",
            "office_name": "Bangalore",
            "timestamp": "2026-10-07T11:00:00+05:30",
            "status": "HEALTHY",
            "diagnosis": "All network health checks are operating normally.",
            "checks": {
                "internet": "UP",
                "gateway": "UP",
                "dns": "OK",
                "packet_loss": 0,
                "latency": 31,
                "download": 94,
                "upload": 21,
            },
        }),
    }
    result = lambda_handler(test_event)
    print("Lambda Result:", json.dumps(result, indent=2))
