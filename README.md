<<<<<<< HEAD
# erpnext_chatgpt
=======
# 🚀 Enterprise AI & ChatGPT Copilot for ERPNext / Frappe v16

A secure, zero-data-breach, production-grade AI Copilot for **ERPNext** and **Frappe Framework v16**. Built to satisfy strict corporate governance, compliance, data masking, and cost-control requirements.

---

## 🛡️ Enterprise Architecture & Security (Zero-Breach Guarantee)

1. **Server-Side Key Isolation:**
   - OpenAI / Anthropic API keys are stored in encrypted `Password` fields inside `AI Settings`.
   - Keys are **never** exposed to client-side JavaScript or the browser.
2. **Permission-Respecting Context:**
   - Strictly enforces Frappe ORM access checks (`has_permission`, `frappe.get_list`).
   - Never bypasses security or executes unauthenticated reads.
3. **Automated PII & Sensitive Data Masking:**
   - Real-time regex sanitization before LLM transmission:
     - **PAN Card & GSTIN** (Tax IDs)
     - **Credit / Debit Card Numbers**
     - **Bank Account Numbers**
     - **Aadhaar / National ID**
   - Strips system metadata, passwords, and authorization tokens.
4. **Prompt Injection Protection:**
   - Scans and blocks malicious system-override attempts (`ignore previous instructions`).
5. **Read-Only Tool Calling:**
   - Native Frappe ORM functions for real-time stock balances (`get_stock_balance`), customer overdues (`get_customer_outstanding`), and sales summaries (`get_sales_summary`).
   - Write operations create **DRAFTS ONLY (`docstatus=0`)** requiring human review and submission.
6. **Cost Control & Governance:**
   - **Monthly Budget Cap (USD):** Automatic hard stop when the site hits the monthly threshold.
   - **Daily Per-User Quota:** Prevents token abuse.
   - **AI Request Log:** Tracks exact latency, prompt tokens, completion tokens, and real dollar cost per invocation.
   - **Pluggable Providers:** Supports **OpenAI**, **Azure OpenAI**, **Anthropic**, and **local Ollama** (100% on-premises data isolation).
7. **Async Reliability:**
   - Background job queuing via `frappe.enqueue` with realtime push via WebSockets (`frappe.publish_realtime`).
   - Automated retries with exponential backoff for HTTP 429 (Rate Limits) and 5xx errors.

---

## 📦 App Structure

```text
F:\erpnext_chatgpt\
├── pyproject.toml
├── README.md
└── erpnext_chatgpt/
    ├── __init__.py
    ├── hooks.py                           # Desk widgets, JS & CSS injection
    ├── security.py                        # PII masking (PAN, GSTIN, Cards, Accounts) & injection filters
    ├── tools.py                           # Safe read-only ORM tools & draft creators
    ├── providers.py                       # Pluggable LLM router (OpenAI, Azure, Anthropic, Ollama)
    ├── api.py                             # Whitelisted endpoints, audit logging & async workers
    ├── tests/
    │   └── test_ai.py                     # Mocked unit tests
    ├── public/
    │   ├── css/chatgpt_widget.css         # Modern glassmorphism UI, light/dark mode
    │   └── js/
    │       ├── chatgpt_widget.js          # Global floating AI Copilot with feedback & shortcuts
    │       └── chatgpt_doctype_actions.js # Form button injector & prompt runner
    └── erpnext_chatgpt/
        ├── doctype/
        │   ├── ai_settings/               # Primary configuration, budget caps & emergency switch
        │   ├── ai_request_log/            # Full audit trail, tokens, costs, latency & user feedback
        │   ├── prompt_template/           # Code-free Jinja prompt presets per DocType
        │   ├── chatgpt_conversation/      # Persistent chat sessions
        │   └── chatgpt_message/           # Individual chat messages child table
        └── page/
            └── chatgpt_copilot/           # Dedicated 2-column ChatGPT workspace
```

---

## 🛠️ Installation Guide for ERPNext v16

### Option A: From Git Repository (Recommended)
```bash
# Push F:\erpnext_chatgpt to your Git server, then run on bench:
bench get-app https://github.com/<your-repo>/erpnext_chatgpt.git
bench --site <your-site-name> install-app erpnext_chatgpt
bench --site <your-site-name> migrate
bench restart
```

### Option B: Local App Link
```bash
# Copy F:\erpnext_chatgpt into your frappe-bench/apps/erpnext_chatgpt
./env/bin/pip install -e ./apps/erpnext_chatgpt
bench --site <your-site-name> install-app erpnext_chatgpt
bench --site <your-site-name> migrate
bench restart
```

---

## ⚙️ Initial Configuration

1. Log into ERPNext Desk as **System Manager**.
2. In the Awesomebar (`Ctrl + K`), search **`AI Settings`**.
3. Select your provider:
   - **OpenAI:** Enter your OpenAI API key and choose model (`gpt-4o-mini`, `gpt-4o`).
   - **Ollama / Local:** Set base URL to `http://localhost:11434/v1` (no external API call, 100% private).
4. Configure limits:
   - **Monthly Budget Cap (USD):** E.g. `$50.00`
   - **Max Requests / User / Day:** E.g. `100`
   - **Mask Sensitive Data:** Checked (Active)
5. Click **`Test Provider Connection`** at the top right to verify.
6. Click **Save**.

---

## 🧪 Running Unit Tests
```bash
bench --site <your-site-name> run-tests --app erpnext_chatgpt
```
Tests data masking regex, prompt injection blocks, token cost calculators, and mocked LLM responses without consuming API credits.
>>>>>>> e49c9c6 (feat: complete enterprise ChatGPT and AI Copilot integration for Frappe v16)
