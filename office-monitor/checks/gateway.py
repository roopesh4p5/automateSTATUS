"""Default gateway detection and health check."""

import logging
import platform
import re
import socket
import subprocess
from typing import Any, Dict, Optional

from .ping_utils import execute_ping, parse_ping_output

logger = logging.getLogger(__name__)


def find_default_gateway() -> Optional[str]:
    """Detect the IPv4 default gateway address across Windows, macOS, and Linux."""
    system = platform.system().lower()

    if system == "windows":
        # 1. Try route print 0.0.0.0
        try:
            res = subprocess.run(
                ["route", "print", "0.0.0.0"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=4,
                check=False,
            )
            # Find lines like: 0.0.0.0          0.0.0.0      192.168.1.1    192.168.1.50     25
            for line in res.stdout.splitlines():
                parts = line.strip().split()
                if len(parts) >= 3 and parts[0] == "0.0.0.0" and parts[1] == "0.0.0.0":
                    gw = parts[2]
                    if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", gw) and gw != "0.0.0.0":
                        return gw
        except Exception as e:
            logger.debug("Windows route print failed: %s", e)

        # 2. Try ipconfig
        try:
            res = subprocess.run(
                ["ipconfig"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=4,
                check=False,
            )
            match = re.search(
                r"Default Gateway[ .]*:\s*([0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})",
                res.stdout,
                re.IGNORECASE,
            )
            if match and match.group(1) != "0.0.0.0":
                return match.group(1)
        except Exception as e:
            logger.debug("Windows ipconfig failed: %s", e)

    elif system == "darwin":  # macOS
        # 1. Try route -n get default
        try:
            res = subprocess.run(
                ["route", "-n", "get", "default"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=4,
                check=False,
            )
            match = re.search(r"gateway:\s*([0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})", res.stdout)
            if match:
                return match.group(1)
        except Exception as e:
            logger.debug("macOS route get default failed: %s", e)

        # 2. Try netstat -nr
        try:
            res = subprocess.run(
                ["netstat", "-nr"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=4,
                check=False,
            )
            for line in res.stdout.splitlines():
                if line.startswith("default"):
                    parts = line.split()
                    if len(parts) >= 2 and re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", parts[1]):
                        return parts[1]
        except Exception as e:
            logger.debug("macOS netstat failed: %s", e)

    elif system == "linux":
        # 1. Try /proc/net/route
        try:
            with open("/proc/net/route", "r", encoding="utf-8") as f:
                for line in f.readlines()[1:]:
                    fields = line.strip().split()
                    if len(fields) >= 3 and fields[1] == "00000000":
                        # Gateway is hex in little-endian
                        gw_hex = fields[2]
                        octets = [str(int(gw_hex[i : i + 2], 16)) for i in (6, 4, 2, 0)]
                        gw_ip = ".".join(octets)
                        if gw_ip != "0.0.0.0":
                            return gw_ip
        except Exception as e:
            logger.debug("Linux /proc/net/route failed: %s", e)

        # 2. Try ip route show default
        try:
            res = subprocess.run(
                ["ip", "route", "show", "default"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=4,
                check=False,
            )
            match = re.search(r"default via ([0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})", res.stdout)
            if match:
                return match.group(1)
        except Exception as e:
            logger.debug("Linux ip route failed: %s", e)

    # Universal heuristic fallback via UDP socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        parts = local_ip.split(".")
        if len(parts) == 4:
            return f"{parts[0]}.{parts[1]}.{parts[2]}.1"
    except Exception:
        pass

    return None


def check_gateway(manual_gateway: Optional[str] = None, attempts: int = 3, timeout_ms: int = 1500) -> Dict[str, Any]:
    """Test local default router/gateway connectivity.

    Args:
        manual_gateway: Optional override gateway IP if hardcoded in config.
        attempts: Number of ping attempts.
        timeout_ms: Timeout per attempt in ms.

    Returns:
        dict: Standardized gateway check result.
    """
    gw_ip = manual_gateway or find_default_gateway()

    if not gw_ip:
        logger.warning("Could not detect local default gateway IP")
        return {
            "status": "UNKNOWN",
            "address": "Unknown",
            "latency_ms": None,
            "classification": "UNKNOWN",
            "details": "Default gateway address could not be determined",
        }

    # Ping the gateway with multiple attempts (PRD Section 25)
    returncode, output = execute_ping(gw_ip, count=attempts, timeout_ms=timeout_ms)
    parsed = parse_ping_output(output, count=attempts)

    if parsed["received"] > 0:
        latency = parsed["avg_ms"] or 1.0
        return {
            "status": "UP",
            "address": gw_ip,
            "latency_ms": latency,
            "classification": "HEALTHY",
            "details": f"Gateway reachable with {latency}ms latency ({parsed['loss_percent']}% loss)",
        }
    else:
        return {
            "status": "DOWN",
            "address": gw_ip,
            "latency_ms": None,
            "classification": "CRITICAL",
            "details": f"Gateway {gw_ip} unreachable across {attempts} ping attempts",
        }
