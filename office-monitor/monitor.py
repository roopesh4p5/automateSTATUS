#!/usr/bin/env python3
"""Office Network Health Monitor.

Executes all 7 network checks from inside the office, evaluates technical health,
and transmits the standardized JSON report to AWS.
"""

import argparse
from datetime import datetime, timedelta, timezone
import json
import logging
import os
import sys
import time
from typing import Any, Dict

# Support running directly or as a module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from checks.dns import check_dns
from checks.gateway import check_gateway
from checks.internet import check_internet
from checks.latency import check_latency_and_loss
from checks.speed import check_speed
from utils.classifier import evaluate_technical_state
from utils.reporting import send_report

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "monitor.log")

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding="utf-8", mode="a"),
    ],
)
logger = logging.getLogger("OfficeMonitor")


def load_config(config_path: str = "config.json") -> Dict[str, Any]:
    """Load configuration with environment variable overrides."""
    config: Dict[str, Any] = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception as e:
            logger.warning("Could not read %s, using defaults: %s", config_path, e)

    # Environment variable overrides (PRD Section 15, 18, 30)
    config["office_id"] = os.environ.get("OFFICE_ID", config.get("office_id", "bangalore"))
    config["office_name"] = os.environ.get("OFFICE_NAME", config.get("office_name", "Bangalore"))
    config["aws_endpoint"] = os.environ.get("AWS_ENDPOINT", config.get("aws_endpoint", ""))
    config["api_key"] = os.environ.get("API_KEY", config.get("api_key", ""))
    config["check_interval_minutes"] = int(
        os.environ.get("CHECK_INTERVAL_MINUTES", config.get("check_interval_minutes", 10))
    )

    return config


def get_iso_timestamp() -> str:
    """Generate ISO 8601 timestamp with local timezone offset."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def run_checks(config: Dict[str, Any], skip_speed: bool = False) -> Dict[str, Any]:
    """Run all 7 network checks and assemble standardized result payload."""
    office_id = config.get("office_id", "bangalore")
    office_name = config.get("office_name", "Bangalore")
    targets = config.get("targets", {})
    thresholds = config.get("thresholds", {})
    speed_cfg = config.get("speed_test", {})

    logger.info("=== Starting Network Health Checks for Office: %s (%s) ===", office_name, office_id)

    # 1. Router / Gateway Check
    logger.info("[1/7] Checking default router/gateway...")
    gateway_res = check_gateway()
    logger.info("  Gateway Status: %s (Address: %s, Latency: %sms)", gateway_res["status"], gateway_res["address"], gateway_res["latency_ms"])

    # 2. DNS Resolution Check
    logger.info("[2/7] Checking DNS resolution...")
    dns_res = check_dns(targets=targets.get("dns_targets"))
    logger.info("  DNS Status: %s (Avg lookup: %sms)", dns_res["status"], dns_res["avg_resolution_ms"])

    # 3. Internet Reachability Check
    logger.info("[3/7] Checking internet connectivity...")
    internet_res = check_internet(
        ip_targets=targets.get("ping_targets"),
        http_targets=targets.get("http_targets"),
        dns_status=dns_res["status"],
    )
    logger.info("  Internet Status: %s (%s)", internet_res["status"], internet_res["details"])

    # 4 & 5. Latency and Packet Loss Checks
    logger.info("[4/7 & 5/7] Measuring packet loss and round-trip latency...")
    latency_loss_res = check_latency_and_loss(
        targets=targets.get("ping_targets"),
        packet_loss_thresholds=thresholds.get("packet_loss"),
        latency_thresholds=thresholds.get("latency_ms"),
    )
    logger.info(
        "  Latency: %sms (%s), Packet Loss: %s%% (%s)",
        latency_loss_res["latency_ms"],
        latency_loss_res["latency_classification"],
        latency_loss_res["packet_loss_percent"],
        latency_loss_res["packet_loss_classification"],
    )

    # 6 & 7. Download and Upload Speed Tests
    speed_enabled = speed_cfg.get("enabled", True) and not skip_speed and internet_res["status"] != "DOWN"
    if speed_enabled:
        logger.info("[6/7 & 7/7] Measuring download and upload speeds (controlled lightweight test)...")
        speed_res = check_speed(
            download_url=speed_cfg.get("download_url", "https://speed.cloudflare.com/__down?bytes=10000000"),
            upload_url=speed_cfg.get("upload_url", "https://speed.cloudflare.com/__up"),
            download_bytes=speed_cfg.get("download_bytes", 10485760),
            upload_bytes=speed_cfg.get("upload_bytes", 2097152),
            timeout_sec=speed_cfg.get("timeout_seconds", 15.0),
            download_min_mbps=thresholds.get("download_mbps", {}).get("warning_min", 20.0),
            upload_min_mbps=thresholds.get("upload_mbps", {}).get("warning_min", 5.0),
        )
        logger.info(
            "  Download: %s Mbps (%s), Upload: %s Mbps (%s)",
            speed_res["download_mbps"],
            speed_res["download_classification"],
            speed_res["upload_mbps"],
            speed_res["upload_classification"],
        )
    else:
        logger.info("[6/7 & 7/7] Speed test skipped (%s)", "Internet DOWN" if internet_res["status"] == "DOWN" else "Flag or config disabled")
        speed_res = {
            "download_mbps": None,
            "download_classification": "UNKNOWN",
            "download_details": {"error": "Skipped"},
            "upload_mbps": None,
            "upload_classification": "UNKNOWN",
            "upload_details": {"error": "Skipped"},
        }

    # Evaluate Technical State (PRD Section 13 & 26)
    overall_status, diagnosis, classifications = evaluate_technical_state(
        internet=internet_res,
        gateway=gateway_res,
        dns=dns_res,
        latency_loss=latency_loss_res,
        speed=speed_res,
    )
    logger.info("=== Technical State: %s | Diagnosis: %s ===", overall_status, diagnosis)

    # Build Standardized Result Payload (PRD Section 12 & Section 17)
    timestamp = get_iso_timestamp()
    result_payload = {
        "office_id": office_id,
        "office_name": office_name,
        "timestamp": timestamp,
        "status": overall_status,
        "diagnosis": diagnosis,
        "classifications": classifications,
        # Section 12 structure
        "internet": {
            "status": internet_res["status"],
            "classification": classifications["internet"],
            "details": internet_res["details"],
        },
        "gateway": {
            "status": gateway_res["status"],
            "address": gateway_res["address"],
            "latency_ms": gateway_res["latency_ms"],
            "classification": classifications["gateway"],
        },
        "dns": {
            "status": dns_res["status"],
            "classification": classifications["dns"],
            "avg_resolution_ms": dns_res["avg_resolution_ms"],
        },
        "packet_loss_percent": latency_loss_res["packet_loss_percent"],
        "latency_ms": latency_loss_res["latency_ms"],
        "download_mbps": speed_res["download_mbps"],
        "upload_mbps": speed_res["upload_mbps"],
        # Section 17 summary dictionary
        "checks": {
            "internet": internet_res["status"],
            "gateway": gateway_res["status"],
            "dns": dns_res["status"],
            "packet_loss": latency_loss_res["packet_loss_percent"],
            "latency": latency_loss_res["latency_ms"],
            "download": speed_res["download_mbps"],
            "upload": speed_res["upload_mbps"],
        },
    }

    return result_payload


def print_summary_table(result: Dict[str, Any]) -> None:
    """Print readable table of the 7 checks in console."""
    status_emojis = {
        "HEALTHY": "🟢",
        "UP": "🟢",
        "OK": "🟢",
        "WARNING": "🟡",
        "DEGRADED": "🟡",
        "PARTIALLY AVAILABLE": "🟡",
        "CRITICAL": "🔴",
        "DOWN": "🔴",
        "FAILED": "🔴",
        "UNKNOWN": "⚪",
    }

    def emoji(val: Any) -> str:
        return status_emojis.get(str(val).upper(), "⚪")

    c = result.get("checks", {})
    classes = result.get("classifications", {})

    print("\n" + "=" * 55)
    print(f" OFFICE NETWORK HEALTH REPORT: {result.get('office_name')} ({result.get('office_id')})")
    print(f" Timestamp: {result.get('timestamp')}")
    print(f" Overall Status: {emoji(result.get('status'))} {result.get('status')}")
    print(f" Diagnosis: {result.get('diagnosis')}")
    print("-" * 55)
    print(f" {'Check':<20} | {'Value':<18} | {'Status'}")
    print("-" * 55)
    print(f" {'Internet':<20} | {str(c.get('internet')):<18} | {emoji(classes.get('internet'))} {classes.get('internet')}")
    print(f" {'Router/Gateway':<20} | {str(c.get('gateway')):<18} | {emoji(classes.get('gateway'))} {classes.get('gateway')}")
    print(f" {'DNS':<20} | {str(c.get('dns')):<18} | {emoji(classes.get('dns'))} {classes.get('dns')}")
    print(f" {'Packet Loss':<20} | {str(c.get('packet_loss')) + '%':<18} | {emoji(classes.get('packet_loss'))} {classes.get('packet_loss')}")
    print(f" {'Latency':<20} | {str(c.get('latency')) + ' ms':<18} | {emoji(classes.get('latency'))} {classes.get('latency')}")
    dl_val = f"{c.get('download')} Mbps" if c.get('download') is not None else "N/A"
    ul_val = f"{c.get('upload')} Mbps" if c.get('upload') is not None else "N/A"
    print(f" {'Download Speed':<20} | {dl_val:<18} | {emoji(classes.get('download'))} {classes.get('download')}")
    print(f" {'Upload Speed':<20} | {ul_val:<18} | {emoji(classes.get('upload'))} {classes.get('upload')}")
    print("=" * 55 + "\n")


def execute_cycle(
    config: Dict[str, Any],
    quick: bool = False,
    dry_run: bool = False,
    json_output: bool = False,
) -> int:
    """Run one full network check cycle and report to AWS."""
    result = run_checks(config, skip_speed=quick)

    if json_output:
        print(json.dumps(result, indent=2))
    else:
        print_summary_table(result)

    endpoint = config.get("aws_endpoint")
    if not dry_run and endpoint:
        logger.info("Transmitting report to AWS endpoint: %s", endpoint)
        send_res = send_report(
            endpoint=endpoint,
            payload=result,
            api_key=config.get("api_key"),
        )
        if send_res["success"]:
            logger.info("Report delivered successfully to AWS!")
            return 0
        else:
            logger.error("Failed to transmit report to AWS: %s", send_res["error"])
            return 1
    elif dry_run:
        logger.info("Dry-run mode: skipping AWS transmission.")
        return 0
    else:
        logger.warning("No aws_endpoint configured. Skipping transmission.")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Office Network Health Monitor")
    parser.add_argument("--config", "-c", default="config.json", help="Path to config.json")
    parser.add_argument("--dry-run", action="store_true", help="Run checks without sending to AWS")
    parser.add_argument("--quick", action="store_true", help="Skip bandwidth speed test for quick check")
    parser.add_argument("--json", action="store_true", help="Output raw JSON to stdout")
    parser.add_argument("--loop", "-l", action="store_true", help="Run continuously in a loop at the specified interval")
    parser.add_argument("--interval", "-i", type=int, default=None, help="Check interval in minutes (default: config.json or 10)")
    args = parser.parse_args()

    # Load configuration
    cfg_file = args.config if os.path.isabs(args.config) else os.path.join(os.path.dirname(__file__), args.config)
    config = load_config(cfg_file)

    interval_minutes = args.interval or config.get("check_interval_minutes", 10)

    if args.loop:
        logger.info("Continuous monitoring loop started (every %d min). Press Ctrl+C to stop.", interval_minutes)
        last_exit = 0
        try:
            while True:
                last_exit = execute_cycle(config, quick=args.quick, dry_run=args.dry_run, json_output=args.json)
                next_time = (datetime.now() + timedelta(minutes=interval_minutes)).strftime("%H:%M:%S")
                logger.info("Next check scheduled in %d minutes (at %s). Sleeping...", interval_minutes, next_time)
                time.sleep(interval_minutes * 60)
        except KeyboardInterrupt:
            logger.info("Monitoring loop stopped by user.")
            return 0
        return last_exit

    return execute_cycle(config, quick=args.quick, dry_run=args.dry_run, json_output=args.json)


if __name__ == "__main__":
    sys.exit(main())
