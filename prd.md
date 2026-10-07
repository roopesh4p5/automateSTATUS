PRD — Multi-Office Internet & Network Health Monitor

Version: 1.0
Phase: MVP
Initial deployment: Bangalore
Future office: Mangalore
Primary device: Windows laptop in each office server room
Language: Python
Dashboard: None
Historical database: None

1. Objective

Build a lightweight network-health monitoring system that runs from inside each office and checks the office's actual internet connection every hour.

The system must:

Run from the office network.
Check network health.
Send the results securely to AWS.
Have Grok summarize the results.
Have Grok recommend actions when something is wrong.
Send a clean email report.
Support multiple offices.
Initially operate only for Bangalore.
Later add Mangalore without changing the architecture.
Store no historical monitoring data.
2. High-Level Architecture
                         INTERNET
                            │
                    ┌───────┴───────┐
                    │                │
              AWS Infrastructure    Grok API
                    │
                    │
              Email Service
                    │
                    ▼
              Your Email Inbox


BANGALORE OFFICE
────────────────────────────────────────

        ISP
         │
      Router
         │
       Switch
         │
         ├──── Cameras / NVR
         │
         └──── Windows Laptop
                   │
                   │ Network tests
                   │
                   ▼
              Python Agent
                   │
                   │ HTTPS
                   ▼
                AWS API


MANGALORE OFFICE
────────────────────────────────────────

        ISP
         │
      Router
         │
       Switch
         │
         └──── Windows Laptop
                   │
                   ▼
              Python Agent
                   │
                   │ HTTPS
                   ▼
                AWS API

The critical architectural principle is:

Network measurements happen inside the office.

AWS cannot accurately determine whether Bangalore's ISP is working by testing from AWS.

3. Components
Office-side

Each office gets a small Python application.

office-monitor/
│
├── monitor.py
├── config.json
├── requirements.txt
├── checks/
│   ├── internet.py
│   ├── gateway.py
│   ├── dns.py
│   ├── latency.py
│   └── speed.py
│
└── utils/
    └── reporting.py

Initially:

Bangalore laptop
      ↓
Python monitor

Later:

Bangalore laptop → AWS
Mangalore laptop → AWS
4. Office Configuration

The same software should work for every office.

Example:

{
  "office_id": "bangalore",
  "office_name": "Bangalore",
  "aws_endpoint": "https://example.execute-api.region.amazonaws.com/health",
  "check_interval_minutes": 60
}

Mangalore would only require:

{
  "office_id": "mangalore",
  "office_name": "Mangalore"
}

No separate codebase.

5. Monitoring Requirements

The system must perform these checks.

5.1 Internet Up/Down

Determine whether the office has working internet connectivity.

Example:

Internet: UP

or:

Internet: DOWN

The check should not rely on only one external host.

Use multiple reliable targets where practical.

Example:

1.1.1.1
8.8.8.8
HTTPS endpoint

This prevents one external service being down from incorrectly reporting an office outage.

6. Router/Gateway

Determine the local default gateway.

Example:

Gateway: 192.168.1.1
Status: UP
Latency: 1 ms

If the gateway cannot be reached:

Router/Gateway: DOWN

This should be treated differently from an ISP outage.

Example:

Gateway DOWN
Internet DOWN

Likely:

Local network/router problem.

Whereas:

Gateway UP
Internet DOWN

Likely:

WAN/ISP/internet problem.

7. DNS

Perform DNS resolution from the office.

Example:

DNS: OK

Test something like:

google.com
cloudflare.com

If DNS fails while direct IP connectivity works:

DNS: FAILED
Internet: PARTIALLY AVAILABLE

This distinction is important.

8. Packet Loss

Measure packet loss to reliable external targets.

Example:

Packet Loss: 0%

Example warning:

Packet Loss: 7%

Example critical:

Packet Loss: 20%

Thresholds should be configurable.

Initial recommended thresholds:

Packet loss	Status
0–2%	Healthy
>2–5%	Warning
>5–10%	Degraded
>10%	Critical

These are starting thresholds, not absolute network standards.

9. Latency

Measure round-trip latency.

Example:

Latency: 32 ms

Suggested initial thresholds:

Latency	Status
<100 ms	Healthy
100–200 ms	Warning
200–300 ms	Degraded
>300 ms	Critical

Again, these should be configurable.

10. Download Speed

The laptop should perform an actual download test.

Example:

Download: 92 Mbps

The test must be lightweight enough that it doesn't unnecessarily consume office bandwidth.

The PRD should therefore define:

limited test duration
limited test payload
configurable test size
timeout
failure handling
Important

A speed test necessarily needs an internet endpoint to transfer data.

Therefore "self-contained" should mean:

No paid speed-test SaaS/API dependency.

It cannot mean:

No external internet endpoint whatsoever.

11. Upload Speed

Same principle.

Example:

Upload: 18 Mbps

The test should:

use a controlled payload
have a timeout
avoid continuously consuming bandwidth
report failure separately from internet outage
12. Result Object

The Python agent should produce a standardized result.

Example:

{
  "office_id": "bangalore",
  "timestamp": "2026-10-07T11:00:00+05:30",

  "internet": {
    "status": "UP"
  },

  "gateway": {
    "status": "UP",
    "address": "192.168.1.1"
  },

  "dns": {
    "status": "OK"
  },

  "packet_loss_percent": 0,

  "latency_ms": 31,

  "download_mbps": 94.2,

  "upload_mbps": 21.4
}
13. Critical Detection

The Python monitoring system, not Grok, should determine the technical state.

For example:

Internet DOWN
        ↓
CRITICAL

or:

Gateway UP
Internet DOWN
        ↓
Likely ISP/WAN problem

or:

Gateway DOWN
Internet DOWN
        ↓
Likely local router/network problem

This prevents an LLM from deciding whether an outage actually occurred.

14. Grok's Responsibility

Grok receives the structured monitoring results.

Its job is:

Summarize

Example:

Bangalore internet is currently degraded. Internet connectivity is available, but latency is elevated at 320 ms and packet loss is 8%.

Recommend action

Example:

Action needed: Check the WAN/ISP connection and router logs. If packet loss persists across the next check, contact the ISP.

Grok should not invent measurements.

The prompt should explicitly tell it:

Use only the supplied monitoring data. Do not invent values, events, causes, or measurements.

15. Grok Free Model

The system should make the Grok model configurable through an environment variable.

Example:

GROK_MODEL=...

This means you can change models later without modifying application code.

The API key must never be placed directly in the Python source code.

Use environment variables:

GROK_API_KEY
16. AWS Architecture

Since you want the cheapest practical deployment, I recommend a serverless architecture rather than keeping an EC2 instance running 24/7.

Office Laptop
     │
     │ HTTPS POST
     ▼
API Gateway
     │
     ▼
AWS Lambda
     │
     ├──── Grok API
     │
     └──── Email provider

No EC2 server needs to stay running.

Why this architecture?

You have only two offices and only one report per hour.

Your workload is tiny.

A continuously running EC2 server would be unnecessary for the MVP.

17. AWS API

The office laptop sends:

POST /health

Example:

{
  "office_id": "bangalore",
  "timestamp": "...",
  "checks": {
    "internet": "UP",
    "gateway": "UP",
    "dns": "OK",
    "packet_loss": 0,
    "latency": 31,
    "download": 94,
    "upload": 21
  }
}

AWS validates the request.

18. Authentication

The office laptop must authenticate with AWS.

Do not expose an unauthenticated endpoint.

For MVP:

Office Laptop
      │
      │ HTTPS + secret/API authentication
      ▼
API Gateway

Each office can have its own secret.

Example:

BANGALORE_API_KEY
MANGALORE_API_KEY

This also makes revoking one office's access easy.

19. No Database

Per your requirement:

No historical storage.

Therefore:

Laptop
   ↓
AWS
   ↓
Grok
   ↓
Email
   ↓
Discard

There is no requirement for:

RDS
DynamoDB
S3
Elasticsearch
dashboard database

CloudWatch/application logs may still exist for troubleshooting depending on AWS defaults/configuration, but the application does not maintain monitoring history.

20. Email

Since you're flexible between EmailJS and SMTP, I recommend making the email provider configurable.

The application should have an email abstraction:

EmailService
     │
     ├── EmailJS
     │
     └── SMTP

For the MVP, we can choose whichever is simplest and cheapest after implementation.

The important thing is that the rest of the application does not depend on the specific email provider.

21. Email Format

The email should contain all offices in one report.

Example:

Subject:

Office Network Health Report — 07 Oct 2026 11:00
Report
Check	Bangalore	Mangalore
Internet	🟢 UP	🟢 UP
Router/Gateway	🟢 UP	🟢 UP
DNS	🟢 OK	🟢 OK
Packet Loss	0%	1%
Latency	31 ms	45 ms
Download Speed	94 Mbps	87 Mbps
Upload Speed	21 Mbps	19 Mbps

Then:

Summary
Bangalore is operating normally.

Mangalore has slightly elevated latency but remains operational.
Action Needed
No immediate action required.

If something is critical:

Action Needed:

Bangalore internet connectivity is down while the local gateway
remains reachable.

Recommended action:
1. Check WAN/router status.
2. Check ISP connection.
3. Verify router WAN logs.
4. Contact ISP if connectivity does not recover.
22. Multi-Office Aggregation

This is important.

The email should not be generated independently by each office.

Instead:

Bangalore laptop ──┐
                   │
Mangalore laptop ──┼──► AWS
                   │
                   ▼
             Combined report
                   │
                   ▼
                 Grok
                   │
                   ▼
                 Email

That allows one email to contain:

Bangalore
Mangalore
Summary
Action Needed
23. Scheduling

For the office laptop, use Windows Task Scheduler, not AWS scheduling.

Why?

The network test must happen from the office.

Windows Task Scheduler
        │
        │ Every hour
        ▼
Python monitor.py
        │
        ▼
Network tests
        │
        ▼
AWS
Schedule
Every hour
At minute 00

Equivalent to:

01:00
02:00
03:00
04:00
...

No AWS scheduler is necessary for the MVP.

This is both simpler and cheaper.

24. Windows Startup/Recovery

The monitoring agent should be configured so that if the laptop restarts:

Windows boots
     ↓
Task Scheduler
     ↓
Monitoring task
     ↓
Next scheduled check

The task should also be configured to run even if the user is not logged in.

This is important because the laptop is intended to operate as a server-room monitoring device.

25. Network Test Failure Handling

A single failed ping should not immediately mean the office is down.

For example:

Ping #1 → failure
Ping #2 → success
Ping #3 → success

should not trigger a critical outage.

The monitor should perform multiple attempts and calculate the result.

Likewise, speed tests should have timeouts.

26. Recommended Status Model

Each check should have:

HEALTHY
WARNING
CRITICAL
UNKNOWN

Example:

Internet       HEALTHY
Gateway        HEALTHY
DNS            HEALTHY
Packet Loss    WARNING
Latency        WARNING
Download       HEALTHY
Upload         HEALTHY

Overall office status:

HEALTHY
WARNING
CRITICAL

The most severe condition determines the overall status.

27. Security Requirements
Never hard-code:
Grok API key
AWS credentials
Email credentials
EmailJS private credentials

Use environment variables or a secure configuration mechanism.

Office → AWS

Only outbound HTTPS should be required.

No port forwarding.

No public exposure of:

office router
NVR
cameras
laptop

This is one of the major advantages of the proposed architecture.

28. MVP Scope
Included
Windows laptop agent
Python
Bangalore office
Mangalore-ready architecture
Internet check
Gateway check
DNS check
Packet loss
Latency
Download speed
Upload speed
AWS serverless API
Grok summarization
Grok recommendations
Email report
One combined report
Hourly execution
No database
No dashboard
Explicitly excluded
Dashboard
Historical analytics
Mobile app
SMS
WhatsApp
Camera health monitoring
NVR monitoring
Router configuration
Automatic ISP ticket creation
Automatic network remediation
29. MVP Flow

The final system should behave like this:

                    EVERY HOUR
                         │
                         ▼
              Windows Task Scheduler
                         │
                         ▼
                  Python Agent
                         │
             ┌───────────┼───────────┐
             ▼           ▼           ▼
          Gateway       DNS       Internet
             │           │           │
             └───────────┼───────────┘
                         │
                    Latency/Loss
                         │
                  Speed Test
                         │
                         ▼
                 Create JSON
                         │
                         ▼
                    AWS API
                         │
                         ▼
                 Validate request
                         │
                         ▼
                 Grok Free Model
                         │
                         ├── Summary
                         │
                         └── Actions
                         │
                         ▼
                   Email Service
                         │
                         ▼
                     YOUR EMAIL
30. Initial Bangalore Deployment

The first deployment should be deliberately simple:

Bangalore Windows Laptop
        │
        ▼
Install Python
        │
        ▼
Install monitor
        │
        ▼
Configure:
    OFFICE_ID=bangalore
        │
        ▼
Run manually
        │
        ▼
Verify network results
        │
        ▼
Send to AWS
        │
        ▼
Verify Grok response
        │
        ▼
Verify email
        │
        ▼
Enable hourly Task Scheduler

Only after this works should we install the exact same agent for Mangalore.

31. Definition of Done

The MVP is considered complete when:

Bangalore laptop can run the Python monitor.
All seven network checks return results.
Results are correctly classified.
Bangalore can securely send results to AWS.
AWS can process the result.
Grok can summarize the supplied data.
Grok can recommend actions for abnormal conditions.
An email arrives containing the report.
The email contains the seven metrics.
The email contains Summary.
The email contains Action Needed.
The system runs automatically every hour.
No inbound connection to the Bangalore office is required.
Mangalore can be added through configuration rather than a new application.
Recommended final technology stack
Component	Choice
Office agent	Python
Office OS	Windows
Scheduling	Windows Task Scheduler
AWS API	API Gateway
AWS compute	Lambda
Database	None
AI	Grok free model initially
Email	EmailJS or SMTP abstraction
Dashboard	None
Monitoring location	Inside each office
Initial office	Bangalore
Future office	Mangalore
Historical data	None