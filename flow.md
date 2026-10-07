# Multi-Office Network Health Monitor — Execution Flow & Trigger Architecture

This document details the complete end-to-end execution flow, scheduling triggers, and data pipeline of the monitoring system.

---

## 1. How It Gets Triggered

The critical architectural principle is that **measurements happen from inside the office LAN**. External cloud servers cannot accurately determine if the office's local ISP is down by probing from the outside.

Therefore, the system is triggered **locally on the server room laptop** every hour:

```mermaid
flowchart TD
    subgraph Trigger_Sources["Trigger Mechanisms"]
        T1["Hourly Schedule (Minute 00 of Every Hour)"]
        T2["Missed Task Catch-up (Post-Reboot / Power Recovery)"]
        T3["Manual Operator Run (python monitor.py)"]
    end

    subgraph Laptop["Windows Server Room Laptop"]
        TS["Windows Task Scheduler\n(Task: OfficeNetworkHealthMonitor)\n- Runs whether user logged in or not\n- Highest Privileges (SYSTEM / Admin)"]
        PY["Python Agent\n(monitor.py)"]
    end

    subgraph AWS["AWS Cloud (Serverless)"]
        APIGW["AWS API Gateway\nPOST /health"]
        LMB["AWS Lambda Function\n(lambda_function.lambda_handler)"]
    end

    subgraph External["External Integrations"]
        GROQ["Groq Cloud API\n(llama-3.3-70b-versatile)"]
        EMAIL["Email Provider\n(SMTP / EmailJS)"]
        INBOX["Network Operations Team Inbox"]
    end

    T1 --> TS
    T2 --> TS
    T3 --> PY

    TS -->|Spawns python.exe| PY
    PY -->|Executes 7 network tests| PY
    PY -->|Outbound HTTPS POST with X-API-Key| APIGW
    APIGW -->|Proxies event| LMB
    LMB -->|Sends metrics for summarization| GROQ
    GROQ -->|Returns Summary & Actions| LMB
    LMB -->|Dispatches formatted HTML report| EMAIL
    EMAIL --> INBOX
```

---

## 2. End-to-End Sequence Diagram

This sequence diagram illustrates the lifecycle of a single hourly check from kickoff to report delivery:

```mermaid
sequenceDiagram
    autonumber
    participant Sch as Windows Task Scheduler
    participant Mon as monitor.py (Office Agent)
    participant Net as Local LAN & ISP
    participant GW as AWS API Gateway
    participant Lam as AWS Lambda
    participant Groq as Groq API (xAI/Groq)
    participant Mail as Email Service (SMTP/EmailJS)
    participant User as Operations Inbox

    Note over Sch,Mon: Trigger Phase (Every Hour at :00)
    Sch->>Mon: Execute `python.exe monitor.py` in C:\office-monitor
    activate Mon

    Note over Mon,Net: In-Office Network Testing Phase
    Mon->>Net: 1. Auto-detect default gateway IP & ping (gateway.py)
    Net-->>Mon: Gateway UP/DOWN, latency_ms
    Mon->>Net: 2. Resolve DNS for google.com & cloudflare.com (dns.py)
    Net-->>Mon: Resolved IPs, avg_lookup_ms
    Mon->>Net: 3. Verify external internet reachability across 1.1.1.1, 8.8.8.8, HTTPS (internet.py)
    Net-->>Mon: Reachable count, UP/DOWN/PARTIALLY AVAILABLE
    Mon->>Net: 4 & 5. Measure roundtrip latency & packet loss with 10 pings (latency.py)
    Net-->>Mon: avg_latency_ms, packet_loss_percent
    Mon->>Net: 6 & 7. Stream lightweight test payload for download & upload speed (speed.py)
    Net-->>Mon: download_mbps, upload_mbps

    Note over Mon: Local Classification Phase
    Mon->>Mon: evaluate_technical_state() (classifier.py)<br/>- Determines technical fault (Local vs ISP)<br/>- Assigns HEALTHY / WARNING / CRITICAL

    Note over Mon,GW: Reporting Phase (Outbound Only)
    Mon->>GW: HTTPS POST /health + X-API-Key (reporting.py)
    deactivate Mon
    activate GW

    GW->>Lam: Invoke lambda_handler(event)
    activate Lam

    Note over Lam: Cloud Ingestion & Authentication
    Lam->>Lam: validate_api_key(headers, office_id)<br/>Checks BANGALORE_API_KEY
    alt Unauthorized
        Lam-->>GW: HTTP 401 Unauthorized
        GW-->>Mon: 401 Error
    else Authorized
        Note over Lam,Groq: AI Summarization Phase
        Lam->>Groq: POST /chat/completions (llama-3.3-70b-versatile)<br/>Passes structured metrics + strict no-hallucination guardrail
        Groq-->>Lam: Factual Summary & Action Needed

        Note over Lam,Mail: Notification Phase
        Lam->>Lam: format_email_report()<br/>Generates PRD Section 21 multi-office table + badges
        Lam->>Mail: send_email(subject, html, text, recipients)
        Mail-->>Lam: 200 OK / Success
        Mail->>User: Delivers "Office Network Health Report — DD Mon YYYY HH:MM"

        Note over Lam: Zero-Database Cleanup
        Lam->>Lam: Discard payload from memory (No historical DB)
        Lam-->>GW: HTTP 200 {"status": "success", "email_dispatched": true}
        deactivate Lam
        GW-->>Mon: HTTP 200 Response
        deactivate GW
    end
```

---

## 3. In-Office Agent Execution Flow (`monitor.py`)

When `monitor.py` starts, it executes tests in a strict topological order so earlier tests inform downstream checks:

```mermaid
flowchart TD
    Start(["Agent Invocation"]) --> LoadCfg["1. Load config.json & Env Overrides"]
    LoadCfg --> ChkGW["2. Router/Gateway Check (gateway.py)\n- Parses OS route table\n- Pings gateway IP with 3 attempts"]
    
    ChkGW --> ChkDNS["3. DNS Resolution Check (dns.py)\n- Resolves google.com & cloudflare.com\n- Measures resolution time"]
    
    ChkDNS --> ChkInet["4. Internet Reachability Check (internet.py)\n- Probes 1.1.1.1, 8.8.8.8, HTTPS endpoints\n- Flags PARTIALLY AVAILABLE if DNS fails"]
    
    ChkInet --> ChkLat["5. Latency & Packet Loss Check (latency.py)\n- Sends 10 ICMP/TCP pings across targets\n- Computes loss % and average RTT ms"]
    
    ChkLat --> InetCondition{"Is Internet UP?"}
    InetCondition -- Yes --> RunSpeed["6. Bandwidth Speed Test (speed.py)\n- Controlled 10MB download streaming\n- Controlled 2MB upload payload\n- Strict 15s timeout"]
    InetCondition -- No --> SkipSpeed["Skip Bandwidth Test\n(Mark UNKNOWN, prevent hanging)"]
    
    RunSpeed --> Classify["7. Technical Classifier (classifier.py)\n- Evaluates root cause\n- Computes overall office status"]
    SkipSpeed --> Classify

    Classify --> DecisionTree{"Technical State Determination"}
    DecisionTree -->|GW DOWN + Inet DOWN| LocalRouter["Diagnosis: Local router / switch failure"]
    DecisionTree -->|GW UP + Inet DOWN| WANOutage["Diagnosis: ISP / WAN uplink outage"]
    DecisionTree -->|Inet UP + DNS FAILED| DNSOutage["Diagnosis: Office DNS resolution failure"]
    DecisionTree -->|High loss / latency| Degraded["Diagnosis: Network degradation"]
    DecisionTree -->|All passed thresholds| Healthy["Diagnosis: All checks healthy"]

    LocalRouter --> FormatJSON["Assemble Standardized JSON Payload"]
    WANOutage --> FormatJSON
    DNSOutage --> FormatJSON
    Degraded --> FormatJSON
    Healthy --> FormatJSON

    FormatJSON --> PrintTable["Print Formatted Console Table"]
    PrintTable --> SendAWS{"aws_endpoint configured?"}
    SendAWS -- Yes --> PostAWS["HTTPS POST to AWS API Gateway (reporting.py)"]
    SendAWS -- No / DryRun --> Done(["Finish Execution (Exit 0)"])
    PostAWS --> Done
```

---

## 4. AWS Serverless Backend Processing Flow (`lambda_function.py`)

```mermaid
flowchart TD
    Req["Incoming HTTP POST /health"] --> ParseBody["Extract Headers & Parse JSON Body"]
    ParseBody --> ValidateAuth{"Validate X-API-Key Header\nagainst BANGALORE_API_KEY"}
    
    ValidateAuth -- Invalid --> Err401["Return HTTP 401 Unauthorized\n(Reject request)"]
    ValidateAuth -- Valid --> CheckOffices["Normalize Office Payloads\n(Single office or Multi-office batch)"]
    
    CheckOffices --> GroqCall{"GROQ_API_KEY present?"}
    GroqCall -- Yes --> CallGroqAPI["Call Groq OpenAI API\n(https://api.groq.com/openai/v1)\n- System prompt: Grounded strictly in metrics\n- Model: llama-3.3-70b-versatile"]
    GroqCall -- No / Fails --> RuleFallback["Run Built-in Rule-Based Engine\n- Generates deterministic Summary & Actions"]
    
    CallGroqAPI --> ParseResponse["Parse into 'Summary' and 'Action Needed'"]
    RuleFallback --> ParseResponse
    
    ParseResponse --> RenderTemplate["Render Email Template (template.py)\n- PRD Section 21 Subject: Office Network Health Report — DD Mon YYYY HH:MM\n- Multi-office table columns: Check | Bangalore | Mangalore\n- Visual status badges: 🟢 🟡 🔴\n- Action Needed callout box"]
    
    RenderTemplate --> SelectEmailProvider{"EMAIL_PROVIDER Setting"}
    SelectEmailProvider -- "smtp" --> SendSMTP["Send via SmtpEmailService\n(Gmail / AWS SES with TLS)"]
    SelectEmailProvider -- "emailjs" --> SendEmailJS["Send via EmailJSService\n(EmailJS REST API)"]
    SelectEmailProvider -- "mock" --> SendMock["Send via MockEmailService\n(Log to console/memory for tests)"]
    
    SendSMTP --> SuccessResp["Return HTTP 200 OK\nDiscard payload from memory\n(Zero database storage)"]
    SendEmailJS --> SuccessResp
    SendMock --> SuccessResp
```

---

## 5. Failure Modes & Automatic Recovery

| Scenario | What Happens | Automatic Recovery / Behavior |
|---|---|---|
| **Power Outage in Office** | Laptop turns off when battery drains. No reports sent to AWS. | Once power returns, the laptop powers on automatically via **BIOS AC Power Recovery**. Windows boots to lock screen. |
| **Laptop Reboots** | System restarts for Windows updates or reboot. | **Windows Task Scheduler** runs `monitor.py` even without user login (`/ru SYSTEM`). |
| **Check Missed While Off** | Laptop was off during scheduled hour (e.g., at 02:00). | The Task Scheduler setting *"Run task as soon as possible after a scheduled start is missed"* triggers `monitor.py` immediately when Windows boots. |
| **ISP / WAN Cable Cut** | Gateway is reachable (`192.168.1.1` UP), but internet targets fail (`1.1.1.1` DOWN). | Agent classifies state as **CRITICAL - ISP / WAN outage**. When internet restores, next hourly check sends recovery report. |
| **Router Locked Up / Frozen** | Gateway IP is unreachable (`DOWN`). | Agent classifies state as **CRITICAL - Local router / switch failure**, distinguishing it from an external ISP issue. |
| **Groq API Temporary Outage** | Groq Cloud returns 5xx or times out. | Backend falls back instantly to the **deterministic rule-based generator**; email report is delivered without interruption. |
| **Temporary WiFi / LAN Glitch** | A single ping packet drops. | The agent performs multiple attempts (PRD Section 25) before classifying any check as failed. |
