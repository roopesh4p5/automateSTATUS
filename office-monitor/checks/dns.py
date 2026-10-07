"""DNS resolution check."""

import logging
import socket
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_DNS_TARGETS = ["google.com", "cloudflare.com"]


def check_dns(targets: Optional[List[str]] = None, timeout_sec: float = 3.0) -> Dict[str, Any]:
    """Test DNS resolution from inside the office network.

    Args:
        targets: List of domain names to resolve (e.g. ['google.com', 'cloudflare.com']).
        timeout_sec: Timeout for DNS lookup.

    Returns:
        dict: Standardized DNS check result.
    """
    targets = targets or DEFAULT_DNS_TARGETS
    resolved = []
    failed = []
    latencies = []

    old_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(timeout_sec)

    try:
        for domain in targets:
            start_time = time.perf_counter()
            try:
                ip_list = socket.gethostbyname_ex(domain)[2]
                duration_ms = (time.perf_counter() - start_time) * 1000.0
                if ip_list:
                    resolved.append({"domain": domain, "ips": ip_list, "resolution_ms": round(duration_ms, 2)})
                    latencies.append(duration_ms)
                else:
                    failed.append(domain)
            except Exception as e:
                logger.debug("DNS resolution failed for %s: %s", domain, e)
                failed.append(domain)
    finally:
        socket.setdefaulttimeout(old_timeout)

    total = len(targets)
    success_count = len(resolved)
    avg_ms = round(sum(latencies) / len(latencies), 2) if latencies else None

    if success_count == total:
        status = "OK"
        classification = "HEALTHY"
        details = f"All {total} domains resolved successfully (avg {avg_ms}ms)"
    elif success_count > 0:
        status = "DEGRADED"
        classification = "WARNING"
        details = f"{success_count}/{total} domains resolved. Failed: {', '.join(failed)}"
    else:
        status = "FAILED"
        classification = "CRITICAL"
        details = f"All {total} domain lookups failed"

    return {
        "status": status,
        "classification": classification,
        "resolved": resolved,
        "failed": failed,
        "avg_resolution_ms": avg_ms,
        "details": details,
    }
