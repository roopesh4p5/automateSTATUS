"""External internet connectivity check across multiple redundant targets."""

import logging
import ssl
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from .ping_utils import execute_ping, parse_ping_output, tcp_ping

logger = logging.getLogger(__name__)

DEFAULT_IP_TARGETS = ["1.1.1.1", "8.8.8.8"]
DEFAULT_HTTP_TARGETS = ["https://1.1.1.1", "https://8.8.8.8"]


def check_http_endpoint(url: str, timeout_sec: float = 3.0) -> bool:
    """Verify HTTPS endpoint reachability."""
    try:
        ctx = ssl.create_default_context()
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "OfficeNetworkMonitor/1.0"},
            method="HEAD",
        )
        with urllib.request.urlopen(req, timeout=timeout_sec, context=ctx) as response:
            return response.status in (200, 301, 302, 204)
    except urllib.error.HTTPError as e:
        # Any HTTP status response means internet routing works
        return True
    except Exception as e:
        logger.debug("HTTP check failed for %s: %s", url, e)
        return False


def check_internet(
    ip_targets: Optional[List[str]] = None,
    http_targets: Optional[List[str]] = None,
    dns_status: str = "OK",
    attempts_per_target: int = 3,
    timeout_ms: int = 1500,
) -> Dict[str, Any]:
    """Test office internet connectivity using multiple redundant targets.

    Args:
        ip_targets: Direct IP targets (e.g. 1.1.1.1, 8.8.8.8).
        http_targets: HTTPS endpoints (e.g. https://1.1.1.1, https://8.8.8.8).
        dns_status: Status from DNS check ('OK', 'DEGRADED', 'FAILED').
        attempts_per_target: Ping attempts per target.
        timeout_ms: Timeout per attempt.

    Returns:
        dict: Standardized internet check result.
    """
    ip_targets = ip_targets or DEFAULT_IP_TARGETS
    http_targets = http_targets or DEFAULT_HTTP_TARGETS

    results = []
    ip_reachable_count = 0

    # 1. Test direct IP ping / TCP ping
    for ip in ip_targets:
        code, out = execute_ping(ip, count=attempts_per_target, timeout_ms=timeout_ms)
        parsed = parse_ping_output(out, count=attempts_per_target)
        reachable = parsed["received"] > 0
        if not reachable:
            # Fallback to TCP ping on port 53 / 443
            reachable = tcp_ping(ip, port=53, timeout_sec=timeout_ms / 1000.0) is not None

        if reachable:
            ip_reachable_count += 1
        results.append({"target": ip, "type": "ip", "reachable": reachable})

    # 2. Test HTTPS endpoints
    http_reachable_count = 0
    for url in http_targets:
        reachable = check_http_endpoint(url, timeout_sec=max(2.0, timeout_ms / 1000.0))
        if reachable:
            http_reachable_count += 1
        results.append({"target": url, "type": "http", "reachable": reachable})

    total_ip = len(ip_targets)
    has_ip_connectivity = ip_reachable_count > 0
    has_http_connectivity = http_reachable_count > 0

    # Section 7 & 13: DNS failed while direct IP works -> PARTIALLY AVAILABLE
    if has_ip_connectivity and dns_status == "FAILED":
        status = "PARTIALLY AVAILABLE"
        classification = "WARNING"
        details = "Direct IP connectivity available, but DNS resolution is completely failing"
    elif has_ip_connectivity or has_http_connectivity:
        status = "UP"
        classification = "HEALTHY"
        details = f"Internet reachable (IPs: {ip_reachable_count}/{total_ip}, HTTP: {http_reachable_count}/{len(http_targets)})"
    else:
        status = "DOWN"
        classification = "CRITICAL"
        details = "All external targets unreachable"

    return {
        "status": status,
        "classification": classification,
        "details": details,
        "ip_reachable_count": ip_reachable_count,
        "total_ip_targets": total_ip,
        "http_reachable_count": http_reachable_count,
        "total_http_targets": len(http_targets),
        "target_results": results,
    }
