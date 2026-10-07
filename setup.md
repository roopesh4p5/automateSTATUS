# Complete Setup Guide: Multi-Office Network Health Monitor

This guide walks you through setting up the complete network health monitor from start to finish:
1. **Environment Variables**
2. **AWS Lambda & API Gateway Backend**
3. **Office Laptop Setup (Windows Server Room)**
4. **Hourly Windows Task Scheduler Automation**
5. **Adding Future Offices (Mangalore)**

---

## Architecture Flow

```
Inside Office (Bangalore Laptop)
       │
       │ Runs hourly via Windows Task Scheduler
       ▼
  monitor.py
  (Runs 7 network tests inside office LAN)
       │
       │ Outbound HTTPS POST with X-API-Key
       ▼
AWS API Gateway (/health)
       │
       ▼
AWS Lambda
       │
       ├── Groq API (Fast LLM: Summarizes & recommends actions)
       │
       └── Email Service (SMTP or EmailJS)
       │
       ▼
Your Email Inbox
```

---

## 1. Environment Variables Reference

Create a `.env` file or set these in your AWS Lambda configuration:

```env
# ==========================================
# 1. OFFICE AUTHENTICATION (PRD Section 18)
# ==========================================
BANGALORE_API_KEY=your-secret-bangalore-key-123
MANGALORE_API_KEY=your-secret-mangalore-key-456

# ==========================================
# 2. GROQ AI CONFIGURATION (Fast LLM Inference)
# ==========================================
# Get your API key from https://console.groq.com/keys
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxx
GROQ_MODEL=llama-3.3-70b-versatile
# (Optional) GROQ_BASE_URL=https://api.groq.com/openai/v1

# Popular Groq models:
# - llama-3.3-70b-versatile (Recommended)
# - llama-3.1-8b-instant (Fastest, lightweight)

# Note: If GROQ_API_KEY is left empty, the system automatically
# uses an intelligent rule-based summarizer without failing.

# ==========================================
# 3. RECIPIENT EMAIL (PRD Section 21)
# ==========================================
REPORT_RECIPIENTS=your-email@company.com

# ==========================================
# 4. EMAIL PROVIDER (PRD Section 20)
# Choose either 'smtp' or 'emailjs'
# ==========================================
EMAIL_PROVIDER=smtp

# --- IF USING SMTP (e.g. Gmail, Amazon SES, Outlook) ---
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-sender-email@gmail.com
# For Gmail, generate an "App Password" at https://myaccount.google.com/apppasswords
SMTP_PASSWORD=your-16-char-app-password
SMTP_USE_TLS=true
SMTP_FROM_EMAIL=your-sender-email@gmail.com

# --- IF USING EMAILJS (Alternative to SMTP) ---
# EMAIL_PROVIDER=emailjs
# EMAILJS_SERVICE_ID=service_xxxxxxx
# EMAILJS_TEMPLATE_ID=template_xxxxxxx
# EMAILJS_PUBLIC_KEY=xxxxxxxxxxxxxxx
# EMAILJS_PRIVATE_KEY=xxxxxxxxxxxxxxx
```

---

## 2. AWS Lambda & API Gateway Setup

Since the office sends only 1 report per hour, AWS serverless is practically **free** (well within the monthly AWS Free Tier).

### Step 2.1: Package the Lambda Code
On your development machine, package the backend files into a `.zip` file:

```bash
cd aws-backend
zip -r ../lambda_function.zip lambda_function.py groq_service.py grok_service.py template.py email_service/
cd ..
```

*(Note: The Lambda code uses Python's standard library and does not require external pip packages or custom Lambda layers!)*

### Step 2.2: Create the Lambda Function in AWS
1. Open the [AWS Lambda Console](https://console.aws.amazon.com/lambda/).
2. Click **Create function**.
3. Choose **Author from scratch**:
   - **Function name**: `office-network-health-monitor`
   - **Runtime**: `Python 3.11` or `Python 3.12`
   - **Architecture**: `x86_64` or `arm64`
4. Click **Create function**.
5. In the **Code source** section:
   - Click **Upload from** -> **.zip file**.
   - Select the `lambda_function.zip` created in Step 2.1.
   - Click **Save**.
6. In **Runtime settings** (below the code editor):
   - Ensure **Handler** is set to `lambda_function.lambda_handler`.
7. In the **Configuration** tab:
   - Go to **General configuration** -> **Edit**:
     - **Timeout**: Set to `30 seconds` (gives Groq and email enough time to respond).
     - **Memory**: `128 MB` (minimal cost).
   - Go to **Environment variables** -> **Edit** and add:
     - `BANGALORE_API_KEY`: e.g. `secret-bangalore-key-123`
     - `GROQ_API_KEY`: your Groq API key from https://console.groq.com/keys
     - `GROQ_MODEL`: `llama-3.3-70b-versatile` (or `llama-3.1-8b-instant`)
     - `EMAIL_PROVIDER`: `smtp`
     - `SMTP_HOST`: `smtp.gmail.com`
     - `SMTP_PORT`: `587`
     - `SMTP_USERNAME`: `your-sender-email@gmail.com`
     - `SMTP_PASSWORD`: `your-app-password`
     - `REPORT_RECIPIENTS`: `your-inbox@company.com`

---

### Step 2.3: Create the API Gateway Endpoint
1. Open the [AWS API Gateway Console](https://console.aws.amazon.com/apigateway/).
2. Click **Create API**.
3. Under **HTTP API**, click **Build**.
4. In the wizard:
   - **API name**: `office-monitor-api`
   - Click **Add integration**:
     - Integration type: **Lambda**
     - Lambda function: Select `office-network-health-monitor`
5. Configure Routes:
   - **Method**: `POST`
   - **Resource path**: `/health`
   - **Integration target**: `office-network-health-monitor`
6. Stages: Leave as `$default` (with auto-deploy enabled).
7. Click **Create**.
8. Copy your **Invoke URL** from the overview page:
   ```
   https://abc123xyz.execute-api.ap-south-1.amazonaws.com
   ```
   Your full monitoring endpoint is:
   ```
   https://abc123xyz.execute-api.ap-south-1.amazonaws.com/health
   ```

---

## 3. Office Laptop Setup (Bangalore Server Room)

The laptop in the server room performs the 7 network measurements from inside your office network.

### Step 3.1: Install Python on the Windows Laptop
1. Download Python 3.10+ from [python.org](https://www.python.org/downloads/).
2. Run the installer.
3. ⚠️ **IMPORTANT**: Check the box **"Add Python to PATH"** before clicking Install Now.

---

### Step 3.2: Copy Project Files to the Laptop
Create a folder on the Windows laptop, for example:
```
C:\office-monitor\
```
Copy these folders and files from this repo into `C:\office-monitor\`:
```
C:\office-monitor\
├── monitor.py
├── config.json
├── requirements.txt
├── checks\
│   ├── gateway.py
│   ├── dns.py
│   ├── internet.py
│   ├── latency.py
│   ├── speed.py
│   └── ping_utils.py
├── utils\
│   ├── classifier.py
│   └── reporting.py
└── scripts\
    ├── setup_task_windows.ps1
    └── setup_task_windows.bat
```

---

### Step 3.3: Configure `config.json`
Open `C:\office-monitor\config.json` in Notepad and update the endpoint and API key:

```json
{
  "office_id": "bangalore",
  "office_name": "Bangalore",
  "aws_endpoint": "https://abc123xyz.execute-api.ap-south-1.amazonaws.com/health",
  "api_key": "secret-bangalore-key-123",
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

---

### Step 3.4: Test the Agent Manually
Open Command Prompt (`cmd`) on the Windows laptop and run:

```cmd
cd C:\office-monitor
python monitor.py
```

You should see:
```text
[1/7] Checking default router/gateway...
  Gateway Status: UP (Address: 192.168.1.1, Latency: 1.2ms)
[2/7] Checking DNS resolution...
  DNS Status: OK (Avg lookup: 4.1ms)
[3/7] Checking internet connectivity...
  Internet Status: UP
[4/7 & 5/7] Measuring packet loss and round-trip latency...
  Latency: 18.5ms (HEALTHY), Packet Loss: 0.0% (HEALTHY)
[6/7 & 7/7] Measuring download and upload speeds...
  Download: 94.2 Mbps (HEALTHY), Upload: 21.4 Mbps (HEALTHY)

=======================================================
 OFFICE NETWORK HEALTH REPORT: Bangalore (bangalore)
 Overall Status: 🟢 HEALTHY
 Diagnosis: All network health checks are operating normally.
=======================================================
Transmitting report to AWS endpoint: https://.../health
Report delivered successfully to AWS!
```

Check your email inbox — you should receive the formatted report with the 7-check table, Summary, and Action Needed!

---

## 4. Automate with Windows Task Scheduler

Per PRD Section 23 & 24, the laptop must run the check every hour, survive laptop restarts, and run even if no user is logged in.

### Method A: Automated PowerShell Setup (Recommended)
1. On the Windows laptop, search for **PowerShell** in the Start Menu.
2. Right-click **Windows PowerShell** -> **Run as Administrator**.
3. Run:
   ```powershell
   cd C:\office-monitor\scripts
   .\setup_task_windows.ps1 -Action Register
   ```
4. To test trigger immediately:
   ```powershell
   .\setup_task_windows.ps1 -Action RunNow
   ```

### Method B: Automated Batch Setup
1. Right-click `C:\office-monitor\scripts\setup_task_windows.bat` -> **Run as Administrator**.

### Method C: Windows Task Scheduler GUI
If you prefer the graphical interface:
1. Press `Win + R`, type `taskschd.msc`, and press Enter.
2. Click **Create Task** (not Basic Task) in the right sidebar:
   - **General Tab**:
     - Name: `OfficeNetworkHealthMonitor`
     - Check: **"Run whether user is logged on or not"**
     - Check: **"Run with highest privileges"**
   - **Triggers Tab**:
     - Click **New...**
     - Begin the task: **On a schedule** -> **Daily**
     - Under Advanced settings:
       - Check: **Repeat task every**: `1 hour`
       - For a duration of: `Indefinitely`
       - Check: **Enabled**
   - **Actions Tab**:
     - Click **New...**
     - Action: **Start a program**
     - Program/script: `python` (or full path `C:\Users\admin\AppData\Local\Programs\Python\Python311\python.exe`)
     - Add arguments: `"C:\office-monitor\monitor.py"`
     - Start in: `C:\office-monitor`
   - **Settings Tab**:
     - Check: **"Run task as soon as possible after a scheduled start is missed"**
     - Check: **"If the task fails, restart every"**: `5 minutes`, attempt `3 times`
3. Click **OK** and enter the Windows user password when prompted.

---

## 5. Adding Mangalore Office (Future Office)

Per PRD Section 4: **No code changes are needed** to add Mangalore!

1. On the Mangalore Windows laptop, copy the same `C:\office-monitor\` directory.
2. In `config.json`, change only the office ID and key:
   ```json
   {
     "office_id": "mangalore",
     "office_name": "Mangalore",
     "aws_endpoint": "https://abc123xyz.execute-api.ap-south-1.amazonaws.com/health",
     "api_key": "secret-mangalore-key-456"
   }
   ```
3. In AWS Lambda Environment Variables, add:
   - `MANGALORE_API_KEY`: `secret-mangalore-key-456`
4. Register the scheduled task on the Mangalore laptop:
   ```powershell
   .\setup_task_windows.ps1 -Action Register
   ```

---

## 6. Verification Checklist

| Check | Expected Result | Verified? |
|---|---|---|
| Gateway Check | Detects default gateway IP and latency | Yes |
| DNS Check | Resolves `google.com` and `cloudflare.com` | Yes |
| Internet Reachability | Multiple targets (`1.1.1.1`, `8.8.8.8`, HTTP) respond | Yes |
| Packet Loss & Latency | Accurate % loss and RTT ms | Yes |
| Speed Test | Controlled download & upload Mbps | Yes |
| Technical Diagnosis | Differentiates local router fault from ISP WAN outage | Yes |
| Grok Summarization | Generates factual Summary & Actions without hallucinated data | Yes |
| Email Delivery | Email arrives with 7-metric table and status indicators | Yes |
| Windows Scheduling | Runs every hour in background even if laptop reboots | Yes |
