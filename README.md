# Multi-Office Internet & Network Health Monitor

A lightweight, outbound-only network health monitoring system that measures office network connectivity from inside each office server room, transmits structured metrics to AWS, generates AI summaries and action recommendations with Grok, and emails automated hourly reports.

Designed for:
- **Office Devices**: Windows laptops in server rooms (starting with Bangalore, expandable to Mangalore via configuration).
- **AWS Backend**: Serverless AWS Lambda behind API Gateway (cost-effective, zero running EC2 instances, zero database).
- **AI Engine**: Groq (Fast LLM Inference: `llama-3.3-70b-versatile`) for concise status summaries and technical recommendations with strict grounding guardrails.
- **Email Delivery**: Provider-agnostic abstraction supporting **SMTP** and **EmailJS**.

---

## Architecture Overview

```
BANGALORE OFFICE (Windows Laptop)
  │
  ├── 1. Default Router/Gateway Check (IP auto-detection & ping)
  ├── 2. DNS Resolution Check (google.com, cloudflare.com)
  ├── 3. Internet Connectivity Check (1.1.1.1, 8.8.8.8, HTTPS)
  ├── 4. Latency Measurement (round-trip ms)
  ├── 5. Packet Loss Measurement (%)
  ├── 6. Download Speed Test (controlled lightweight payload)
  └── 7. Upload Speed Test (controlled lightweight payload)
  │
  ├── Technical State & Health Classifier (CRITICAL / WARNING / HEALTHY)
  │
  ▼ Outbound HTTPS (X-API-Key Authentication)
AWS API Gateway (`POST /health`)
  │
  ▼
AWS Lambda Function
  │
  ├──── Groq API (Summarization & Actions)
  │
  └──── Email Service (SMTP or EmailJS)
  │
  ▼
Network Operations Email Inbox
```

---

## Repository Structure

```
automateSTATUS/
├── prd.md                                # Product Requirements Document
├── office-monitor/                       # Python agent running on office laptops
│   ├── monitor.py                        # Main CLI & agent runner
│   ├── config.json                       # Office configuration file
│   ├── requirements.txt                  # Agent dependencies (works with stdlib)
│   ├── checks/                           # The 7 core network checks
│   │   ├── gateway.py                    # Auto-detects & tests default gateway
│   │   ├── dns.py                        # Resolves DNS domains
│   │   ├── internet.py                   # Multi-target internet reachability
│   │   ├── latency.py                    # Packet loss and RTT latency
│   │   ├── speed.py                      # Download & upload bandwidth tests
│   │   └── ping_utils.py                 # Cross-platform ping execution
│   ├── utils/
│   │   ├── classifier.py                 # Technical health determination
│   │   └── reporting.py                  # HTTPS delivery to AWS
│   └── scripts/                          # Windows automation & testing scripts
│       ├── setup_task_windows.ps1        # Headless Task Scheduler (PowerShell)
│       ├── setup_task_windows.bat        # Headless Task Scheduler (CMD Batch)
│       ├── run_headless.vbs              # Silent invisible background runner
│       └── test_local_e2e.py             # End-to-end integration test runner
├── aws-backend/                          # Serverless backend
│   ├── lambda_function.py                # Main AWS Lambda handler
│   ├── grok_service.py                   # Grok API integration & prompt guardrails
│   ├── template.py                       # PRD Section 21 email report formatter
│   ├── local_server.py                   # Local API Gateway emulator
│   ├── requirements.txt                  # Backend dependencies
│   └── email_service/                    # Email provider abstraction
│       ├── base.py                       # EmailService abstract interface
│       ├── smtp.py                       # Standard SMTP client (Gmail, SES, etc.)
│       ├── emailjs.py                    # EmailJS REST API client
│       └── mock.py                       # Local simulation & logger
└── tests/                                # Automated unit test suite
    ├── test_checks.py
    ├── test_classifier.py
    ├── test_email.py
    ├── test_grok.py
    └── test_lambda.py
```

---

## 1. Quick Start: Local End-to-End Testing

You can test the entire pipeline locally without AWS or third-party accounts:

### Step 1: Start the Local Backend Emulator
In Terminal 1:
```bash
python3 aws-backend/local_server.py --port 8080
```
This runs a local HTTP server at `http://127.0.0.1:8080/health` simulating AWS API Gateway + Lambda.

### Step 2: Run the Office Monitor Agent
In Terminal 2:
```bash
python3 office-monitor/monitor.py
```
Or for a fast run skipping the bandwidth speed test:
```bash
python3 office-monitor/monitor.py --quick
```

You will see:
1. The 7 checks executing live.
2. The formatted console table.
3. The report sent via HTTP to the local backend.
4. The backend classifying the metrics, summarizing with Grok (or the built-in fallback), formatting the PRD email table, and dispatching via the mock email service.

### Step 3: Run the Automated E2E Test Suite
```bash
python3 office-monitor/scripts/test_local_e2e.py
```
This tests single-office reporting, multi-office aggregation (Bangalore + Mangalore), authentication failure handling, and simulated router outages.

---

## 2. Running Unit Tests

Execute the 25 unit tests covering all checks, thresholds, classifiers, and email formatting:
```bash
python3 -m unittest discover tests
```

---

## 3. Configuration

### Office Monitor (`office-monitor/config.json`)

```json
{
  "office_id": "bangalore",
  "office_name": "Bangalore",
  "aws_endpoint": "https://<your-api-id>.execute-api.<region>.amazonaws.com/health",
  "api_key": "YOUR_OFFICE_SECRET_KEY",
  "check_interval_minutes": 60,
  "targets": {
    "ping_targets": ["1.1.1.1", "8.8.8.8"],
    "dns_targets": ["google.com", "cloudflare.com"],
    "http_targets": ["https://1.1.1.1", "https://8.8.8.8", "https://www.google.com"]
  },
  "thresholds": {
    "packet_loss": { "healthy_max": 2.0, "warning_max": 5.0, "degraded_max": 10.0 },
    "latency_ms": { "healthy_max": 100.0, "warning_max": 200.0, "degraded_max": 300.0 },
    "download_mbps": { "warning_min": 20.0 },
    "upload_mbps": { "warning_min": 5.0 }
  },
  "speed_test": {
    "enabled": true,
    "download_url": "https://speed.cloudflare.com/__down?bytes=10000000",
    "upload_url": "https://speed.cloudflare.com/__up",
    "download_bytes": 10485760,
    "upload_bytes": 2097152,
    "timeout_seconds": 15
  }
}
```

Environment variables can override any config value:
- `OFFICE_ID` (e.g. `bangalore` or `mangalore`)
- `OFFICE_NAME` (e.g. `Bangalore`)
- `AWS_ENDPOINT`
- `API_KEY`

---

### Backend Environment Variables (AWS Lambda)

Set these in your AWS Lambda Function configuration:

#### Authentication & Office Secrets
- `BANGALORE_API_KEY`: Secret key for Bangalore laptop.
- `MANGALORE_API_KEY`: Secret key for Mangalore laptop.
- Or `API_KEY`: Global API key shared across offices.

#### Groq AI Configuration (https://console.groq.com)
- `GROQ_API_KEY`: Your Groq API Key from https://console.groq.com/keys. *(If omitted, uses rule-based generator).*
- `GROQ_MODEL`: Groq model identifier (default: `llama-3.3-70b-versatile` or `llama-3.1-8b-instant`).
- `GROQ_BASE_URL`: Optional custom endpoint (default: `https://api.groq.com/openai/v1`).

#### Email Configuration (Provider Abstraction)
- `REPORT_RECIPIENTS`: Destination email address(es) (comma-separated).
- `EMAIL_PROVIDER`: `smtp` or `emailjs` (default: auto-detected, or `mock` if unset).

**For SMTP (e.g. Gmail, Amazon SES, SendGrid):**
- `SMTP_HOST`: `smtp.gmail.com`
- `SMTP_PORT`: `587`
- `SMTP_USERNAME`: `your-email@gmail.com`
- `SMTP_PASSWORD`: `your-app-password`
- `SMTP_USE_TLS`: `true`
- `SMTP_FROM_EMAIL`: `noc-reports@yourcompany.com`

**For EmailJS:**
- `EMAILJS_SERVICE_ID`: `service_xxxx`
- `EMAILJS_TEMPLATE_ID`: `template_xxxx`
- `EMAILJS_PUBLIC_KEY`: `your_public_key`
- `EMAILJS_PRIVATE_KEY`: `your_private_key`

---

## 4. Deploying to AWS Lambda & API Gateway

1. Package the backend:
   ```bash
   cd aws-backend
   zip -r ../lambda_package.zip lambda_function.py grok_service.py template.py email_service/
   cd ..
   ```
2. In AWS Console:
   - Create a Lambda function with runtime **Python 3.11** or **Python 3.12**.
   - Upload `lambda_package.zip`.
   - Handler: `lambda_function.lambda_handler`.
   - Configure Environment Variables (`BANGALORE_API_KEY`, `GROK_API_KEY`, `SMTP_*`, etc.).
   - Create an **HTTP API Gateway** or **REST API Gateway**:
     - Route: `POST /health`
     - Integration: Lambda Function
     - Deploy stage (`$default` or `prod`).
3. Note your API Gateway URL (e.g. `https://xxxx.execute-api.ap-south-1.amazonaws.com/health`) and paste it into `office-monitor/config.json`.

---

## 5. Setting Up Bangalore Server Room Laptop (Windows)

Follow Section 30 of the PRD:

1. **Install Python 3.9+** on the Bangalore Windows laptop. Ensure "Add Python to PATH" is checked during installation.
2. Copy the `office-monitor/` folder to `C:\office-monitor\` (the `scripts/` folder is included inside).
3. In `C:\office-monitor\config.json`, verify:
   ```json
   "office_id": "bangalore",
   "office_name": "Bangalore",
   "aws_endpoint": "https://your-api-gateway-url/health",
   "api_key": "YOUR_BANGALORE_SECRET"
   ```
4. **Test run manually**:
   ```cmd
   python C:\office-monitor\monitor.py
   ```
   Verify all 7 checks succeed and the email report arrives.
5. **Enable headless Windows Task Scheduler** (PRD Section 23 & 24):
   - Right-click PowerShell -> **Run as Administrator**:
     ```powershell
     cd C:\office-monitor\scripts
     .\setup_task_windows.ps1 -Action Register -IntervalMinutes 10
     ```
   - Or run `setup_task_windows.bat 10`.

The task will run:
- Completely **headlessly** via `pythonw.exe` in Hidden mode (no black terminal or CMD window will ever pop up).
- Every 10 minutes (or every 1 hour in production with `-IntervalMinutes 60`).
- Even if no user is currently logged on.
- Automatically after a laptop restart or power outage.

---

## 6. Adding Mangalore (Future Office)

Per PRD Section 4 & 26: **No codebase changes are required**.
1. Copy `office-monitor/` to the Mangalore server room laptop.
2. In `config.json`, change:
   ```json
   "office_id": "mangalore",
   "office_name": "Mangalore",
   "api_key": "YOUR_MANGALORE_SECRET"
   ```
3. Set `MANGALORE_API_KEY` in AWS Lambda environment variables.
4. Run `setup_task_windows.ps1` on the Mangalore laptop.
