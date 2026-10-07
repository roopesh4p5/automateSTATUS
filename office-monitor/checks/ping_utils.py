"""Cross-platform ping execution and output parsing utility."""

import logging
import platform
import re
import socket
import subprocess
import time
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


def is_windows() -> bool:
    return platform.system().lower() == "windows"


def is_macos() -> bool:
    return platform.system().lower() == "darwin"


def execute_ping(host: str, count: int = 3, timeout_ms: int = 2000) -> Tuple[int, str]:
    """Execute native OS ping command.

    Args:
        host: Target IP address or hostname.
        count: Number of packets to send.
        timeout_ms: Timeout in milliseconds per attempt.

    Returns:
        Tuple of (returncode, stdout_text).
    """
    if is_windows():
        cmd = ["ping", "-n", str(count), "-w", str(timeout_ms), host]
    elif is_macos():
        # macOS ping: -c count, -W waittime in ms (since macOS 10.x, -W is in ms; in older it was ignored or ms)
        cmd = ["ping", "-c", str(count), "-W", str(timeout_ms), host]
    else:
        # Linux ping: -c count, -W waittime in seconds
        timeout_sec = max(1, int(timeout_ms / 1000))
        cmd = ["ping", "-c", str(count), "-W", str(timeout_sec), host]

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=(count * (timeout_ms / 1000.0)) + 3.0,
            check=False,
        )
        return proc.returncode, proc.stdout
    except subprocess.TimeoutExpired:
        logger.warning("Ping command timed out for host %s", host)
        return -1, "Ping command timed out"
    except Exception as exc:
        logger.warning("Ping command error for host %s: %s", host, exc)
        return -1, str(exc)


def parse_ping_output(output: str, count: int) -> Dict[str, Optional[float]]:
    """Parse ping command output for sent, received, packet loss %, and average latency.

    Returns:
        dict: {
            "sent": int,
            "received": int,
            "loss_percent": float,
            "avg_ms": Optional[float]
        }
    """
    res = {
        "sent": count,
        "received": 0,
        "loss_percent": 100.0,
        "avg_ms": None,
    }

    if not output:
        return res

    # 1. Parse packet loss and counts
    # Windows: Packets: Sent = 4, Received = 4, Lost = 0 (0% loss)
    win_packets = re.search(
        r"Packets:\s*Sent\s*=\s*(\d+),\s*Received\s*=\s*(\d+),\s*Lost\s*=\s*(\d+)\s*\(([\d\.]+)%\s*loss\)",
        output,
        re.IGNORECASE,
    )
    if win_packets:
        sent = int(win_packets.group(1))
        received = int(win_packets.group(2))
        loss = float(win_packets.group(4))
        res["sent"] = sent
        res["received"] = received
        res["loss_percent"] = loss

    # Unix: 4 packets transmitted, 4 received, 0% packet loss (or 0.0% packet loss)
    unix_packets = re.search(
        r"(\d+)\s+(?:packets\s+)?transmitted,\s*(\d+)\s+(?:packets\s+)?received,\s*([\d\.]+)%\s+packet\s+loss",
        output,
        re.IGNORECASE,
    )
    if unix_packets:
        sent = int(unix_packets.group(1))
        received = int(unix_packets.group(2))
        loss = float(unix_packets.group(3))
        res["sent"] = sent
        res["received"] = received
        res["loss_percent"] = loss

    # 2. Parse latency
    # Windows: Minimum = 14ms, Maximum = 18ms, Average = 16ms
    win_lat = re.search(r"Average\s*=\s*(\d+)\s*ms", output, re.IGNORECASE)
    if win_lat:
        res["avg_ms"] = float(win_lat.group(1))

    # Unix: round-trip min/avg/max/stddev = 12.345/15.456/18.234/1.5 ms
    # or rtt min/avg/max/mdev = 12.345/15.456/18.234/1.5 ms
    unix_lat = re.search(
        r"(?:round-trip|rtt)\s+min/avg/max/(?:stddev|mdev)\s*=\s*[\d\.]+/([\d\.]+)/[\d\.]+/[\d\.]+\s*ms",
        output,
        re.IGNORECASE,
    )
    if unix_lat:
        res["avg_ms"] = float(unix_lat.group(1))

    # If ping lines show individual replies: "time=12.3 ms" or "time<1ms"
    if res["avg_ms"] is None and res["received"] > 0:
        times = re.findall(r"time[=<]([\d\.]+)\s*ms", output, re.IGNORECASE)
        if times:
            parsed_times = [float(t) for t in times]
            res["avg_ms"] = round(sum(parsed_times) / len(parsed_times), 2)

    return res


def tcp_ping(host: str, port: int = 53, timeout_sec: float = 2.0) -> Optional[float]:
    """Measure TCP handshake round-trip latency to a host and port.

    Used as fallback when ICMP is blocked or not permitted.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout_sec)
    start = time.perf_counter()
    try:
        sock.connect((host, port))
        latency = (time.perf_counter() - start) * 1000.0
        sock.close()
        return round(latency, 2)
    except Exception:
        return None
