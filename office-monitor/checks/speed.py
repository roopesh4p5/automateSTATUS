"""Lightweight, controlled bandwidth speed tests for download and upload.

No paid SaaS dependencies. Uses public CDN endpoints with strict payload caps and timeouts.
"""

import logging
import ssl
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

DEFAULT_DOWNLOAD_URL = "https://speed.cloudflare.com/__down?bytes=10000000"  # 10 MB
DEFAULT_UPLOAD_URL = "https://speed.cloudflare.com/__up"
DEFAULT_DOWNLOAD_BYTES = 10 * 1024 * 1024  # 10 MB max
DEFAULT_UPLOAD_BYTES = 2 * 1024 * 1024  # 2 MB max
DEFAULT_MAX_DURATION_SEC = 10.0  # Stop test after 10s to prevent bandwidth hogging
DEFAULT_TIMEOUT_SEC = 15.0

DEFAULT_DOWNLOAD_MIN_MBPS = 20.0
DEFAULT_UPLOAD_MIN_MBPS = 5.0


def measure_download_speed(
    download_url: str = DEFAULT_DOWNLOAD_URL,
    max_bytes: int = DEFAULT_DOWNLOAD_BYTES,
    max_duration_sec: float = DEFAULT_MAX_DURATION_SEC,
    timeout_sec: float = DEFAULT_TIMEOUT_SEC,
) -> Dict[str, Any]:
    """Measure download speed using a controlled payload and duration cap.

    Returns:
        dict: {"mbps": float or None, "bytes": int, "duration_sec": float, "error": str or None}
    """
    start_time = None
    total_bytes = 0
    chunk_size = 64 * 1024  # 64 KB

    try:
        ctx = ssl.create_default_context()
        req = urllib.request.Request(
            download_url,
            headers={"User-Agent": "OfficeNetworkMonitor/1.0"},
        )
        with urllib.request.urlopen(req, timeout=timeout_sec, context=ctx) as response:
            start_time = time.perf_counter()
            while total_bytes < max_bytes:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                total_bytes += len(chunk)
                elapsed = time.perf_counter() - start_time
                if elapsed >= max_duration_sec:
                    # Duration cap reached: prevent excessive bandwidth consumption
                    break

        duration_sec = time.perf_counter() - start_time
        if duration_sec > 0 and total_bytes > 0:
            mbps = round((total_bytes * 8.0) / (duration_sec * 1_000_000.0), 1)
            return {
                "mbps": mbps,
                "bytes": total_bytes,
                "duration_sec": round(duration_sec, 2),
                "error": None,
            }
        else:
            return {"mbps": None, "bytes": 0, "duration_sec": 0.0, "error": "No data received"}

    except Exception as e:
        logger.warning("Download speed test failed: %s", e)
        return {"mbps": None, "bytes": total_bytes, "duration_sec": 0.0, "error": str(e)}


def measure_upload_speed(
    upload_url: str = DEFAULT_UPLOAD_URL,
    upload_bytes: int = DEFAULT_UPLOAD_BYTES,
    timeout_sec: float = DEFAULT_TIMEOUT_SEC,
) -> Dict[str, Any]:
    """Measure upload speed using a controlled payload and timeout.

    Returns:
        dict: {"mbps": float or None, "bytes": int, "duration_sec": float, "error": str or None}
    """
    try:
        # Generate predictable test payload
        payload = b"0" * upload_bytes
        ctx = ssl.create_default_context()
        req = urllib.request.Request(
            upload_url,
            data=payload,
            headers={
                "User-Agent": "OfficeNetworkMonitor/1.0",
                "Content-Type": "application/octet-stream",
            },
            method="POST",
        )

        start_time = time.perf_counter()
        with urllib.request.urlopen(req, timeout=timeout_sec, context=ctx) as response:
            _ = response.read(1024)
        duration_sec = time.perf_counter() - start_time

        if duration_sec > 0:
            mbps = round((upload_bytes * 8.0) / (duration_sec * 1_000_000.0), 1)
            return {
                "mbps": mbps,
                "bytes": upload_bytes,
                "duration_sec": round(duration_sec, 2),
                "error": None,
            }
        else:
            return {"mbps": None, "bytes": 0, "duration_sec": 0.0, "error": "Instant upload error"}

    except Exception as e:
        logger.warning("Upload speed test failed: %s", e)
        return {"mbps": None, "bytes": 0, "duration_sec": 0.0, "error": str(e)}


def check_speed(
    download_url: str = DEFAULT_DOWNLOAD_URL,
    upload_url: str = DEFAULT_UPLOAD_URL,
    download_bytes: int = DEFAULT_DOWNLOAD_BYTES,
    upload_bytes: int = DEFAULT_UPLOAD_BYTES,
    timeout_sec: float = DEFAULT_TIMEOUT_SEC,
    download_min_mbps: float = DEFAULT_DOWNLOAD_MIN_MBPS,
    upload_min_mbps: float = DEFAULT_UPLOAD_MIN_MBPS,
    skip_upload: bool = False,
) -> Dict[str, Any]:
    """Execute download and upload speed checks with status classification.

    Args:
        download_url: URL for download test.
        upload_url: URL for upload test.
        download_bytes: Max bytes to download.
        upload_bytes: Bytes to upload.
        timeout_sec: Timeout per test.
        download_min_mbps: Minimum healthy download speed.
        upload_min_mbps: Minimum healthy upload speed.
        skip_upload: Whether to skip upload test.

    Returns:
        dict: Standardized speed test result.
    """
    dl_res = measure_download_speed(
        download_url=download_url,
        max_bytes=download_bytes,
        timeout_sec=timeout_sec,
    )

    if not skip_upload and dl_res["error"] is None:
        ul_res = measure_upload_speed(
            upload_url=upload_url,
            upload_bytes=upload_bytes,
            timeout_sec=timeout_sec,
        )
    else:
        ul_res = {"mbps": None, "bytes": 0, "duration_sec": 0.0, "error": dl_res.get("error") or "Skipped"}

    # Classifications
    dl_mbps = dl_res["mbps"]
    ul_mbps = ul_res["mbps"]

    if dl_mbps is not None:
        dl_class = "HEALTHY" if dl_mbps >= download_min_mbps else "WARNING"
    else:
        dl_class = "UNKNOWN"

    if ul_mbps is not None:
        ul_class = "HEALTHY" if ul_mbps >= upload_min_mbps else "WARNING"
    else:
        ul_class = "UNKNOWN"

    return {
        "download_mbps": dl_mbps,
        "download_classification": dl_class,
        "download_details": dl_res,
        "upload_mbps": ul_mbps,
        "upload_classification": ul_class,
        "upload_details": ul_res,
    }
