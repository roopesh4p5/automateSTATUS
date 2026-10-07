"""Grok LLM integration service for network health report summarization."""

import json
import logging
import os
import ssl
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

DEFAULT_GROK_MODEL = "grok-beta"
DEFAULT_GROK_BASE_URL = "https://api.x.ai/v1"


def generate_rule_based_analysis(offices_data: List[Dict[str, Any]]) -> Tuple[str, str]:
    """Fallback generator when Grok API key is not configured or API is unavailable.

    Strictly adheres to supplied data without inventing anything.
    """
    summaries = []
    actions = []

    for office in offices_data:
        name = office.get("office_name", office.get("office_id", "Office"))
        status = office.get("status", "HEALTHY")
        diagnosis = office.get("diagnosis", "")
        c = office.get("checks", {})
        loss = c.get("packet_loss", 0)
        lat = c.get("latency", 0)
        inet = c.get("internet", "UP")
        gw = c.get("gateway", "UP")
        dns = c.get("dns", "OK")

        if status == "HEALTHY":
            summaries.append(f"{name} is operating normally with all 7 network checks healthy.")
        elif status == "WARNING":
            summaries.append(f"{name} network is degraded. {diagnosis}")
        else:
            summaries.append(f"{name} network is experiencing a CRITICAL condition. {diagnosis}")

        if status == "CRITICAL":
            if gw == "DOWN" and inet == "DOWN":
                actions.append(f"{name}: 1. Check local office router and power status.\n2. Verify local server-room switch cables.\n3. Restart router if unreachable.")
            elif gw == "UP" and inet == "DOWN":
                actions.append(f"{name}: 1. Verify router WAN status and ISP uplink LED.\n2. Check router WAN logs for PPPoE/DHCP disconnect.\n3. Contact ISP support if outage persists.")
            elif inet == "PARTIALLY AVAILABLE" or dns == "FAILED":
                actions.append(f"{name}: 1. Verify office DNS server configuration.\n2. Test fallback DNS servers (8.8.8.8, 1.1.1.1).\n3. Flush local DNS cache.")
            else:
                actions.append(f"{name}: Investigate severe network degradation (Latency: {lat}ms, Packet Loss: {loss}%). Contact ISP if sustained.")
        elif status == "WARNING":
            warning_items = []
            if loss and float(loss) > 2.0:
                warning_items.append(f"packet loss is at {loss}%")
            if lat and float(lat) > 100.0:
                warning_items.append(f"latency is elevated at {lat}ms")
            if warning_items:
                actions.append(f"{name}: Monitor connection. {' and '.join(warning_items)}. If condition persists into next hourly check, inspect router WAN traffic.")
            else:
                actions.append(f"{name}: Non-critical warning detected. Monitor across next hourly cycle.")

    summary_text = " ".join(summaries)
    action_text = "\n\n".join(actions) if actions else "No immediate action required."
    return summary_text, action_text


def summarize_with_grok(offices_data: List[Dict[str, Any]]) -> Tuple[str, str]:
    """Call Grok API to summarize monitoring results and recommend actions.

    Follows PRD Section 14 strictly:
    - Use only the supplied monitoring data.
    - Do not invent values, events, causes, or measurements.
    - Configurable model through GROK_MODEL env var (PRD Section 15).
    - Configurable API key through GROK_API_KEY env var (PRD Section 15).

    Returns:
        Tuple[str, str]: (Summary, Action Needed)
    """
    api_key = os.environ.get("GROK_API_KEY")
    model = os.environ.get("GROK_MODEL", DEFAULT_GROK_MODEL)
    base_url = os.environ.get("GROK_BASE_URL", DEFAULT_GROK_BASE_URL).rstrip("/")

    # If no API key provided, fall back to strict rule-based analysis
    if not api_key:
        logger.info("GROK_API_KEY not configured. Using standard rule-based summarizer.")
        return generate_rule_based_analysis(offices_data)

    system_prompt = (
        "You are an expert Network Operations Center (NOC) assistant analyzing network health metrics "
        "for office locations.\n"
        "Your task is to provide two sections:\n"
        "1. Summary: A concise, factual summary (1-2 sentences per office) of current health.\n"
        "2. Action Needed: Specific technical actions if abnormal, or exactly 'No immediate action required.' if healthy.\n\n"
        "STRICT INSTRUCTIONS (PRD Section 14):\n"
        "- Use only the supplied monitoring data.\n"
        "- Do not invent values, events, causes, or measurements.\n"
        "- Format your response strictly with the headings 'Summary:' and 'Action Needed:'."
    )

    prompt_data = []
    for o in offices_data:
        prompt_data.append({
            "office_name": o.get("office_name", o.get("office_id")),
            "office_id": o.get("office_id"),
            "status": o.get("status"),
            "diagnosis": o.get("diagnosis"),
            "checks": o.get("checks"),
            "classifications": o.get("classifications"),
        })

    user_prompt = (
        "Here are the latest hourly network health measurements for our office(s):\n"
        f"{json.dumps(prompt_data, indent=2)}\n\n"
        "Please provide the Summary and Action Needed strictly based on the above data."
    )

    url = f"{base_url}/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 400,
    }

    try:
        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data_bytes,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
                "User-Agent": "OfficeNetworkMonitorBackend/1.0",
            },
            method="POST",
        )
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=20.0, context=ctx) as resp:
            resp_data = json.loads(resp.read().decode("utf-8"))
            content = resp_data["choices"][0]["message"]["content"]
            return parse_grok_response(content, offices_data)

    except Exception as e:
        logger.warning("Failed to invoke Grok API: %s. Using rule-based fallback.", e)
        return generate_rule_based_analysis(offices_data)


def parse_grok_response(content: str, fallback_data: List[Dict[str, Any]]) -> Tuple[str, str]:
    """Parse Grok output into Summary and Action Needed strings."""
    summary = ""
    action_needed = ""

    lines = content.strip().splitlines()
    current_section = None
    summary_lines = []
    action_lines = []

    for line in lines:
        stripped = line.strip()
        lower = stripped.lower()
        if lower.startswith("summary:") or lower == "**summary:**" or lower == "### summary":
            current_section = "summary"
            inline = stripped.split(":", 1)[-1].strip() if ":" in stripped else ""
            if inline:
                summary_lines.append(inline)
            continue
        elif lower.startswith("action needed:") or lower == "**action needed:**" or lower == "### action needed":
            current_section = "action"
            inline = stripped.split(":", 1)[-1].strip() if ":" in stripped else ""
            if inline:
                action_lines.append(inline)
            continue

        if current_section == "summary" and stripped:
            summary_lines.append(stripped)
        elif current_section == "action" and stripped:
            action_lines.append(stripped)

    summary = "\n".join(summary_lines).strip()
    action_needed = "\n".join(action_lines).strip()

    if not summary or not action_needed:
        # If parsing didn't match cleanly, return full content as summary or use fallback
        if not summary:
            summary = content.strip()
        if not action_needed:
            action_needed = "No immediate action required." if "healthy" in summary.lower() else "Check office network status."

    return summary, action_needed
