# System Flowcharts

```
====================================================================================================
                                      1. HOW IT GETS TRIGGERED
====================================================================================================

      [ Scheduled Hourly Trigger ]               [ Power Outage / Laptop Reboot ]
        • Minute :00 of every hour                 • Office power cuts and restores
                    │                                              │
                    │                                              ▼
                    │                                 [ BIOS: AC Power Recovery ]
                    │                                   • Auto power-on hardware
                    │                                              │
                    │                                              ▼
                    │                                [ Windows Boots to Lock Screen ]
                    │                                  • No user login required
                    │                                              │
                    ├──────────────────────────────────────────────┘
                    │
                    ▼
     ┌─────────────────────────────────────────────────────────────────────────────┐
     │                          WINDOWS TASK SCHEDULER                             │
     │                      Task: OfficeNetworkHealthMonitor                       │
     │                                                                             │
     │   • Runs whether user is logged on or not (/ru SYSTEM)                      │
     │   • "Run task as soon as possible after scheduled start missed" enabled     │
     │   • Highest privileges enabled                                              │
     └──────────────────────────────────────┬──────────────────────────────────────┘
                                            │ triggers
                                            ▼
     ┌─────────────────────────────────────────────────────────────────────────────┐
     │                               PYTHON AGENT                                  │
     │                        C:\office-monitor\monitor.py                         │
     └─────────────────────────────────────────────────────────────────────────────┘
```

```
====================================================================================================
                                       2. CODE EXECUTION FLOW
====================================================================================================

     ┌─────────────────────────────────────────────────────────────────────────────┐
     │ 1. OFFICE LAPTOP AGENT (monitor.py)                                         │
     │                                                                             │
     │    [ gateway.py ]   ──► Auto-detects gateway IP & pings (3 attempts)        │
     │          │                                                                  │
     │    [ dns.py ]       ──► Resolves google.com & cloudflare.com                │
     │          │                                                                  │
     │    [ internet.py ]  ──► Tests 1.1.1.1, 8.8.8.8 & HTTPS endpoints            │
     │          │                                                                  │
     │    [ latency.py ]   ──► Sends 10 pings: measures packet loss % & latency ms │
     │          │                                                                  │
     │    [ speed.py ]     ──► Streams 10MB download & 2MB upload (15s timeout)    │
     │          │                                                                  │
     │    [ classifier.py ]──► Determines fault & health: HEALTHY/WARNING/CRITICAL │
     │          │                                                                  │
     │    [ reporting.py ] ──► Formats JSON payload & adds X-API-Key header        │
     └──────────────────────────────────────┬──────────────────────────────────────┘
                                            │
                                            │ Outbound HTTPS POST /health
                                            │ Header: X-API-Key: <SECRET>
                                            │ (No inbound ports opened)
                                            ▼
     ┌─────────────────────────────────────────────────────────────────────────────┐
     │ 2. AWS API GATEWAY                                                          │
     │    Route: POST /health                                                      │
     │    Passes request payload & headers to Lambda                               │
     └──────────────────────────────────────┬──────────────────────────────────────┘
                                            │
                                            ▼
     ┌─────────────────────────────────────────────────────────────────────────────┐
     │ 3. AWS LAMBDA (lambda_function.py)                                          │
     │                                                                             │
     │    [ validate_api_key ] ──► Checks incoming key vs BANGALORE_API_KEY        │
     │             │                                                               │
     │    [ groq_service.py ]  ──► HTTPS POST to https://api.groq.com/openai/v1   │
     │             │               • Model: llama-3.3-70b-versatile                │
     │             │               • Strict rule: Grounded only in supplied data   │
     │             │               • Output: Factual Summary + Action Needed       │
     │             │                                                               │
     │    [ template.py ]      ──► Formats PRD Section 21 report                   │
     │             │               • Table: Check | Bangalore | Mangalore          │
     │             │               • Badges: 🟢 UP / 🟡 WARN / 🔴 CRIT             │
     │             │                                                               │
     │    [ email_service ]    ──► Dispatches report via SMTP (Gmail/SES)          │
     │             │               or EmailJS                                      │
     │             │                                                               │
     │    [ Discard ]          ──► Zero database: discards metrics from memory     │
     └──────────────────────────────────────┬──────────────────────────────────────┘
                                            │
                                            ▼
     ┌─────────────────────────────────────────────────────────────────────────────┐
     │ 4. OPERATIONS INBOX                                                         │
     │                                                                             │
     │    Subject: Office Network Health Report — 07 Oct 2026 11:00                │
     │                                                                             │
     │    Check             | Bangalore     | Mangalore                            │
     │    ------------------+---------------+------------------                     │
     │    Internet          | 🟢 UP         | 🟢 UP                                │
     │    Router/Gateway    | 🟢 UP         | 🟢 UP                                │
     │    DNS               | 🟢 OK         | 🟢 OK                                │
     │    Packet Loss       | 0%            | 1%                                   │
     │    Latency           | 31 ms         | 45 ms                                │
     │    Download Speed    | 94 Mbps       | 87 Mbps                              │
     │    Upload Speed      | 21 Mbps       | 19 Mbps                              │
     │                                                                             │
     │    Summary:                                                                 │
     │    Bangalore is operating normally.                                         │
     │                                                                             │
     │    Action Needed:                                                           │
     │    No immediate action required.                                            │
     └─────────────────────────────────────────────────────────────────────────────┘
```

```
====================================================================================================
                               3. TECHNICAL FAULT DECISION TREE
====================================================================================================

                                 [ Run All 7 Network Checks ]
                                               │
                                               ▼
                                   Is Gateway Pingable?
                                   (192.168.1.1 / .0.1)
                                      /          \
                                YES  /            \  NO
                                    ▼              ▼
                           Is Internet UP?     [ Gateway: DOWN ]
                         (1.1.1.1 / 8.8.8.8)           │
                            /          \               ▼
                      YES  /            \  NO     [ CRITICAL: Local Network / Router Fault ]
                          ▼              ▼        • Local router or server switch down
                     Is DNS OK?    [ Gateway: UP  • Action: Check router power & cables
                     (google.com)  [ Internet: DOWN ]
                       /      \          │
                 YES  /        \ NO      ▼
                     ▼          ▼  [ CRITICAL: ISP / WAN Outage ]
            [ HEALTHY ]         │  • Local router reachable, ISP uplink down
                                ▼  • Action: Inspect WAN LEDs, contact ISP
                  [ PARTIALLY AVAILABLE ]
                  • IP routing works, DNS failed
                  • Action: Check DNS servers / flush DNS
```
