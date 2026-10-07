"""Technical state determination and overall health classification."""

from typing import Any, Dict, Tuple

SEVERITY_ORDER = {
    "CRITICAL": 3,
    "WARNING": 2,
    "UNKNOWN": 1,
    "HEALTHY": 0,
}


def evaluate_technical_state(
    internet: Dict[str, Any],
    gateway: Dict[str, Any],
    dns: Dict[str, Any],
    latency_loss: Dict[str, Any],
    speed: Dict[str, Any],
) -> Tuple[str, str, Dict[str, str]]:
    """Determine the technical state, overall status, and specific diagnosis.

    Enforces PRD Section 13 & 26: The Python monitoring system, not Grok,
    determines the technical state and overall severity.

    Returns:
        Tuple: (overall_status, diagnosis_message, classifications_dict)
    """
    gw_status = gateway.get("status", "UNKNOWN")
    inet_status = internet.get("status", "UNKNOWN")
    dns_status = dns.get("status", "UNKNOWN")

    classifications = {
        "internet": internet.get("classification", "UNKNOWN"),
        "gateway": gateway.get("classification", "UNKNOWN"),
        "dns": dns.get("classification", "UNKNOWN"),
        "packet_loss": latency_loss.get("packet_loss_classification", "UNKNOWN"),
        "latency": latency_loss.get("latency_classification", "UNKNOWN"),
        "download": speed.get("download_classification", "UNKNOWN"),
        "upload": speed.get("upload_classification", "UNKNOWN"),
    }

    # Technical Diagnosis logic (PRD Section 13)
    if gw_status == "DOWN" and inet_status == "DOWN":
        diagnosis = (
            "Likely local network/router problem. Local default gateway is unreachable, "
            "causing total loss of external connectivity."
        )
        classifications["internet"] = "CRITICAL"
        classifications["gateway"] = "CRITICAL"
    elif gw_status == "UP" and inet_status == "DOWN":
        diagnosis = (
            "Likely ISP/WAN outage. Local default gateway is reachable, "
            "but external internet targets cannot be reached."
        )
        classifications["internet"] = "CRITICAL"
    elif inet_status == "PARTIALLY AVAILABLE" or dns_status == "FAILED":
        diagnosis = (
            "DNS service failure. Direct external IP routing is functional, "
            "but office DNS resolution is failing."
        )
    elif classifications["packet_loss"] == "CRITICAL" or classifications["latency"] == "CRITICAL":
        loss = latency_loss.get("packet_loss_percent", 0)
        lat = latency_loss.get("latency_ms", 0)
        diagnosis = f"Severe network degradation detected. Latency: {lat}ms, Packet Loss: {loss}%."
    elif any(c == "WARNING" for c in classifications.values()):
        issues = []
        if classifications["packet_loss"] == "WARNING":
            issues.append(f"packet loss at {latency_loss.get('packet_loss_percent')}%")
        if classifications["latency"] == "WARNING":
            issues.append(f"elevated latency at {latency_loss.get('latency_ms')}ms")
        if classifications["download"] == "WARNING":
            issues.append(f"reduced download speed at {speed.get('download_mbps')} Mbps")
        if classifications["upload"] == "WARNING":
            issues.append(f"reduced upload speed at {speed.get('upload_mbps')} Mbps")
        diagnosis = f"Office network operating with warnings: {', '.join(issues)}."
    else:
        diagnosis = "All network health checks are operating normally."

    # Determine overall office status (PRD Section 26: most severe condition determines overall status)
    overall_status = "HEALTHY"
    highest_severity = 0

    for check_name, check_class in classifications.items():
        # Treat UNKNOWN in speed as non-fatal warning/healthy so missing speed test doesn't break status
        sev = SEVERITY_ORDER.get(check_class, 0)
        if sev > highest_severity:
            highest_severity = sev
            if check_class in ("CRITICAL", "WARNING", "HEALTHY"):
                overall_status = check_class

    return overall_status, diagnosis, classifications
