"""HTTP reporting utility to transmit network health results to AWS API."""

import json
import logging
import ssl
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def send_report(
    endpoint: str,
    payload: Dict[str, Any],
    api_key: Optional[str] = None,
    timeout_sec: float = 15.0,
    retries: int = 2,
) -> Dict[str, Any]:
    """Send structured monitoring result to AWS API Gateway endpoint.

    Args:
        endpoint: Full URL (e.g. https://.../health or http://localhost:8080/health).
        payload: Dict containing standardized monitoring metrics.
        api_key: Secret API key for authentication.
        timeout_sec: Timeout for HTTP request.
        retries: Number of retries on network failure.

    Returns:
        dict: {"success": bool, "status_code": int, "response": dict/str, "error": str/None}
    """
    data_bytes = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "OfficeNetworkMonitor/1.0",
    }
    if api_key:
        headers["X-API-Key"] = api_key
        headers["Authorization"] = f"Bearer {api_key}"

    last_error = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(
                endpoint,
                data=data_bytes,
                headers=headers,
                method="POST",
            )
            # Create SSL context (disables strict verification only if testing on local mock)
            ctx = ssl.create_default_context()

            with urllib.request.urlopen(req, timeout=timeout_sec, context=ctx) as resp:
                resp_code = resp.status
                body = resp.read().decode("utf-8")
                try:
                    resp_json = json.loads(body)
                except Exception:
                    resp_json = {"raw": body}

                logger.info("Successfully sent health report to %s (status %d)", endpoint, resp_code)
                return {
                    "success": 200 <= resp_code < 300,
                    "status_code": resp_code,
                    "response": resp_json,
                    "error": None,
                }
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            logger.error("HTTP error %d sending report: %s", e.code, err_body)
            return {
                "success": False,
                "status_code": e.code,
                "response": err_body,
                "error": f"HTTP {e.code}: {e.reason}",
            }
        except Exception as e:
            last_error = str(e)
            logger.warning("Attempt %d failed to send report to %s: %s", attempt + 1, endpoint, e)

    return {
        "success": False,
        "status_code": 0,
        "response": None,
        "error": f"Failed after {retries + 1} attempts: {last_error}",
    }
