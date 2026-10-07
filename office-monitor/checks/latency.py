"""Latency and packet loss measurement checks."""

import logging
from typing import Any, Dict, List, Optional

from .ping_utils import execute_ping, parse_ping_output, tcp_ping

logger = logging.getLogger(__name__)

DEFAULT_PING_TARGETS = ["1.1.1.1", "8.8.8.8"]

DEFAULT_PACKET_LOSS_THRESHOLDS = {
    "healthy_max": 2.0,
    "warning_max": 5.0,
    "degraded_max": 10.0,
}

DEFAULT_LATENCY_THRESHOLDS = {
    "healthy_max": 100.0,
    "warning_max": 200.0,
    "degraded_max": 300.0,
}


def classify_packet_loss(loss_percent: float, thresholds: Optional[Dict[str, float]] = None) -> str:
    """Classify packet loss status based on configurable thresholds."""
    th = thresholds or DEFAULT_PACKET_LOSS_THRESHOLDS
    if loss_percent <= th.get("healthy_max", 2.0):
        return "HEALTHY"
    elif loss_percent <= th.get("warning_max", 5.0):
        return "WARNING"
    elif loss_percent <= th.get("degraded_max", 10.0):
        return "WARNING"  # In the status model (Healthy, Warning, Critical) degraded maps to Warning/Degraded
    else:
        return "CRITICAL"


def classify_latency(latency_ms: Optional[float], thresholds: Optional[Dict[str, float]] = None) -> str:
    """Classify latency status based on configurable thresholds."""
    if latency_ms is None:
        return "CRITICAL"
    th = thresholds or DEFAULT_LATENCY_THRESHOLDS
    if latency_ms < th.get("healthy_max", 100.0):
        return "HEALTHY"
    elif latency_ms <= th.get("warning_max", 200.0):
        return "WARNING"
    elif latency_ms <= th.get("degraded_max", 300.0):
        return "WARNING"
    else:
        return "CRITICAL"


def check_latency_and_loss(
    targets: Optional[List[str]] = None,
    packets_per_target: int = 5,
    timeout_ms: int = 1500,
    packet_loss_thresholds: Optional[Dict[str, float]] = None,
    latency_thresholds: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Measure round-trip latency and packet loss across multiple external targets.

    Args:
        targets: List of external IP addresses to ping.
        packets_per_target: Number of packets sent to each target.
        timeout_ms: Timeout per packet.
        packet_loss_thresholds: Dict with healthy_max, warning_max, degraded_max.
        latency_thresholds: Dict with healthy_max, warning_max, degraded_max.

    Returns:
        dict: Standardized latency and packet loss metrics.
    """
    targets = targets or DEFAULT_PING_TARGETS
    total_sent = 0
    total_received = 0
    all_latencies = []
    target_results = []

    for host in targets:
        returncode, output = execute_ping(host, count=packets_per_target, timeout_ms=timeout_ms)
        parsed = parse_ping_output(output, count=packets_per_target)

        # Fallback to TCP ping if ICMP got 0 replies (some firewalls block ICMP)
        if parsed["received"] == 0:
            tcp_lat = tcp_ping(host, port=53, timeout_sec=timeout_ms / 1000.0)
            if tcp_lat is not None:
                parsed["received"] = 1
                parsed["sent"] = 1
                parsed["loss_percent"] = 0.0
                parsed["avg_ms"] = tcp_lat

        total_sent += parsed["sent"]
        total_received += parsed["received"]
        if parsed["avg_ms"] is not None:
            all_latencies.append(parsed["avg_ms"])

        target_results.append(
            {
                "target": host,
                "sent": parsed["sent"],
                "received": parsed["received"],
                "loss_percent": parsed["loss_percent"],
                "avg_ms": parsed["avg_ms"],
            }
        )

    # Calculate overall aggregate metrics
    if total_sent > 0:
        overall_loss_percent = round(((total_sent - total_received) / total_sent) * 100.0, 1)
    else:
        overall_loss_percent = 100.0

    avg_latency_ms = round(sum(all_latencies) / len(all_latencies), 1) if all_latencies else None

    loss_classification = classify_packet_loss(overall_loss_percent, packet_loss_thresholds)
    lat_classification = classify_latency(avg_latency_ms, latency_thresholds)

    return {
        "packet_loss_percent": overall_loss_percent,
        "packet_loss_classification": loss_classification,
        "latency_ms": avg_latency_ms,
        "latency_classification": lat_classification,
        "targets": target_results,
        "total_packets_sent": total_sent,
        "total_packets_received": total_received,
    }
