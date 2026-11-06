app_name = "erpnext_chatgpt"
app_title = "ERPNext ChatGPT Copilot"
app_publisher = "Antigravity AI"
app_description = "Intelligent ChatGPT Assistant & Copilot for ERPNext / Frappe v16"
app_email = "support@example.com"
app_license = "MIT"
app_version = "1.0.0"

# Scheduled Daily Executive Morning Briefing at 9:00 AM
scheduler_events = {
    "cron": {
        "0 9 * * *": [
            "erpnext_chatgpt.briefing.send_daily_executive_briefing"
        ]
    }
}
