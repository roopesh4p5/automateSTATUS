"""Email template formatter for multi-office network health reports."""

from datetime import datetime
from typing import Any, Dict, List, Tuple


def get_status_indicator(status_val: Any, classification: str = "") -> str:
    """Format status with appropriate emoji indicator."""
    val_str = str(status_val).strip()
    class_str = (classification or val_str).upper()

    if class_str in ("HEALTHY", "UP", "OK"):
        return f"🟢 {val_str}"
    elif class_str in ("WARNING", "DEGRADED", "PARTIALLY AVAILABLE"):
        return f"🟡 {val_str}"
    elif class_str in ("CRITICAL", "DOWN", "FAILED"):
        return f"🔴 {val_str}"
    else:
        return f"⚪ {val_str}"


def format_subject(timestamp_str: str) -> str:
    """Generate subject line according to PRD Section 21:

    Office Network Health Report — DD Mon YYYY HH:MM
    """
    try:
        dt = datetime.fromisoformat(timestamp_str)
        formatted_date = dt.strftime("%d %b %Y %H:%M")
    except Exception:
        formatted_date = timestamp_str

    return f"Office Network Health Report — {formatted_date}"


def format_email_report(
    offices: List[Dict[str, Any]],
    summary: str,
    action_needed: str,
) -> Tuple[str, str, str]:
    """Format network health report into subject, HTML body, and Plain-text body.

    Supports dynamic multi-office columns (PRD Section 21 & 22).

    Args:
        offices: List of standardized office result objects.
        summary: Grok-generated or rule-based summary.
        action_needed: Grok-generated or rule-based action recommendations.

    Returns:
        Tuple[str, str, str]: (subject, html_content, text_content)
    """
    first_timestamp = offices[0].get("timestamp", datetime.now().isoformat()) if offices else datetime.now().isoformat()
    subject = format_subject(first_timestamp)

    # Metric rows definition
    metrics = [
        ("Internet", "internet"),
        ("Router/Gateway", "gateway"),
        ("DNS", "dns"),
        ("Packet Loss", "packet_loss"),
        ("Latency", "latency"),
        ("Download Speed", "download"),
        ("Upload Speed", "upload"),
    ]

    office_names = [o.get("office_name", o.get("office_id", "Office")) for o in offices]

    # Helper to extract metric display string
    def get_metric_display(office: Dict[str, Any], metric_key: str) -> str:
        checks = office.get("checks", {})
        classes = office.get("classifications", {})

        if metric_key == "internet":
            val = checks.get("internet", office.get("internet", {}).get("status", "N/A"))
            cls = classes.get("internet", "")
            return get_status_indicator(val, cls)

        elif metric_key == "gateway":
            val = checks.get("gateway", office.get("gateway", {}).get("status", "N/A"))
            cls = classes.get("gateway", "")
            return get_status_indicator(val, cls)

        elif metric_key == "dns":
            val = checks.get("dns", office.get("dns", {}).get("status", "N/A"))
            cls = classes.get("dns", "")
            return get_status_indicator(val, cls)

        elif metric_key == "packet_loss":
            loss = checks.get("packet_loss", office.get("packet_loss_percent"))
            cls = classes.get("packet_loss", "")
            val = f"{loss}%" if loss is not None else "N/A"
            if cls in ("WARNING", "CRITICAL"):
                return f"⚠️ {val}"
            return val

        elif metric_key == "latency":
            lat = checks.get("latency", office.get("latency_ms"))
            cls = classes.get("latency", "")
            val = f"{lat} ms" if lat is not None else "N/A"
            if cls in ("WARNING", "CRITICAL"):
                return f"⚠️ {val}"
            return val

        elif metric_key == "download":
            dl = checks.get("download", office.get("download_mbps"))
            cls = classes.get("download", "")
            val = f"{dl} Mbps" if dl is not None else "N/A"
            if cls == "WARNING":
                return f"⚠️ {val}"
            return val

        elif metric_key == "upload":
            ul = checks.get("upload", office.get("upload_mbps"))
            cls = classes.get("upload", "")
            val = f"{ul} Mbps" if ul is not None else "N/A"
            if cls == "WARNING":
                return f"⚠️ {val}"
            return val

        return "N/A"

    # 1. Plain Text Construction
    text_lines = [
        f"Subject: {subject}",
        "",
        "Report:",
    ]
    # Header row
    col_w_check = 18
    col_w_office = 18
    header_parts = [f"{'Check':<{col_w_check}}"] + [f"{name:<{col_w_office}}" for name in office_names]
    text_lines.append(" | ".join(header_parts))
    text_lines.append("-" * (col_w_check + len(office_names) * (col_w_office + 3)))

    for label, key in metrics:
        row_vals = [f"{label:<{col_w_check}}"]
        for o in offices:
            display_val = get_metric_display(o, key)
            row_vals.append(f"{display_val:<{col_w_office}}")
        text_lines.append(" | ".join(row_vals))

    text_lines.extend([
        "",
        "Summary:",
        summary.strip(),
        "",
        "Action Needed:",
        action_needed.strip(),
        "",
        "---",
        "Generated automatically by Office Network Health Monitor",
    ])
    text_content = "\n".join(text_lines)

    # 2. HTML Construction
    th_cells = "".join(f"<th style='padding: 10px 16px; background-color: #f1f5f9; text-align: left; font-weight: 600; border-bottom: 2px solid #cbd5e1;'>{name}</th>" for name in office_names)
    html_rows = []
    for label, key in metrics:
        td_cells = "".join(f"<td style='padding: 10px 16px; border-bottom: 1px solid #e2e8f0;'>{get_metric_display(o, key)}</td>" for o in offices)
        html_rows.append(f"<tr><td style='padding: 10px 16px; font-weight: 600; border-bottom: 1px solid #e2e8f0; background-color: #f8fafc;'>{label}</td>{td_cells}</tr>")

    summary_html = summary.strip().replace("\n", "<br>")
    action_html = action_needed.strip().replace("\n", "<br>")

    # Determine alert box color based on actions
    is_healthy = "no immediate action required" in action_needed.lower()
    action_bg = "#f0fdf4" if is_healthy else "#fef2f2"
    action_border = "#86efac" if is_healthy else "#fca5a5"
    action_title_color = "#166534" if is_healthy else "#991b1b"

    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{subject}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.5; color: #1e293b; margin: 0; padding: 24px; background-color: #f8fafc; }}
    .container {{ max-width: 680px; margin: 0 auto; background: #ffffff; border-radius: 8px; border: 1px solid #e2e8f0; padding: 28px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }}
    h2 {{ margin-top: 0; color: #0f172a; font-size: 20px; border-bottom: 1px solid #e2e8f0; padding-bottom: 12px; }}
    table {{ width: 100%; border-collapse: collapse; margin: 20px 0; font-size: 14px; }}
    .section-title {{ font-size: 16px; font-weight: 600; color: #0f172a; margin-top: 24px; margin-bottom: 8px; }}
    .card {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 16px; margin-bottom: 16px; font-size: 14px; line-height: 1.6; }}
    .action-card {{ background: {action_bg}; border: 1px solid {action_border}; border-radius: 6px; padding: 16px; margin-top: 12px; font-size: 14px; line-height: 1.6; color: {action_title_color}; }}
    .footer {{ margin-top: 28px; padding-top: 16px; border-top: 1px solid #e2e8f0; font-size: 12px; color: #64748b; text-align: center; }}
  </style>
</head>
<body>
  <div class="container">
    <h2>{subject}</h2>
    
    <table>
      <thead>
        <tr>
          <th style="padding: 10px 16px; background-color: #f1f5f9; text-align: left; font-weight: 600; border-bottom: 2px solid #cbd5e1;">Check</th>
          {th_cells}
        </tr>
      </thead>
      <tbody>
        {"".join(html_rows)}
      </tbody>
    </table>

    <div class="section-title">Summary</div>
    <div class="card">
      {summary_html}
    </div>

    <div class="section-title">Action Needed</div>
    <div class="action-card">
      {action_html}
    </div>

    <div class="footer">
      Office Network Health Monitor &bull; Automated Hourly Report &bull; No Inbound Connections Required
    </div>
  </div>
</body>
</html>
"""
    return subject, html_content, text_content
