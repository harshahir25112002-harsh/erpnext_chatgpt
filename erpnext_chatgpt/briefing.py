# Copyright (c) 2026, Antigravity AI and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, nowdate, get_url
from erpnext_chatgpt.providers import execute_chat_completion

def send_daily_executive_briefing():
    """
    Automated daily 9:00 AM Cron Task.
    Aggregates financial positions, overdue collections, delayed POs, and open issues,
    synthesizes a high-level briefing via AI, and delivers native notifications.
    """
    settings = frappe.get_single("AI Settings")
    if not settings.enabled or settings.site_disabled:
        return

    today = nowdate()

    # 1. Collections Expected
    open_receivables = frappe.db.sql("""
        SELECT SUM(outstanding_amount) as total, COUNT(name) as count
        FROM `tabSales Invoice`
        WHERE docstatus = 1 AND outstanding_amount > 0 AND due_date <= %s
    """, (today,), as_dict=True)[0]
    rec_total = flt(open_receivables.get("total") or 0.0)
    rec_count = open_receivables.get("count") or 0

    # 2. Vendor Payables Due
    open_payables = frappe.db.sql("""
        SELECT SUM(outstanding_amount) as total, COUNT(name) as count
        FROM `tabPurchase Invoice`
        WHERE docstatus = 1 AND outstanding_amount > 0 AND due_date <= %s
    """, (today,), as_dict=True)[0]
    pay_total = flt(open_payables.get("total") or 0.0)
    pay_count = open_payables.get("count") or 0

    # 3. Delayed Purchase Orders
    delayed_pos = frappe.db.count("Purchase Order", filters={
        "docstatus": 1,
        "status": ["in", ["To Receive and Bill", "To Receive"]],
        "schedule_date": ["<", today]
    })

    # 4. Critical Support Issues
    urgent_issues = frappe.db.count("Issue", filters={
        "status": "Open",
        "priority": ["in", ["High", "Urgent"]]
    }) if frappe.db.exists("DocType", "Issue") else 0

    currency = frappe.defaults.get_global_default("currency") or "USD"

    # Context for AI synthesis
    stats_text = (
        f"Date: {today}\n"
        f"- Overdue Customer Receivables: {currency} {rec_total:,.2f} ({rec_count} invoices)\n"
        f"- Overdue Vendor Payables: {currency} {pay_total:,.2f} ({pay_count} invoices)\n"
        f"- Delayed Purchase Orders: {delayed_pos}\n"
        f"- Urgent Open Support Issues: {urgent_issues}\n"
    )

    prompt = (
        "You are an executive Chief of Staff. Synthesize this raw ERP operational data "
        "into a crisp, 4-bullet executive morning briefing with actionable priority recommendations. "
        "Keep it professional, direct, and under 120 words.\n\n"
        f"{stats_text}"
    )

    try:
        messages = [
            {"role": "system", "content": "You are a concise executive advisor for ERPNext leadership."},
            {"role": "user", "content": prompt}
        ]
        res = execute_chat_completion(messages, model_override=None)
        ai_briefing = res.get("content", stats_text)

        # Deliver to System Managers via Frappe Notification Log
        recipients = frappe.get_all(
            "Has Role",
            filters={"role": "System Manager", "parenttype": "User"},
            pluck="parent"
        )
        # Deduplicate and filter active users
        active_recipients = frappe.get_all(
            "User",
            filters={"name": ["in", list(set(recipients))], "enabled": 1},
            pluck="name"
        )

        for user in active_recipients:
            doc = frappe.new_doc("Notification Log")
            doc.subject = _("🌅 AI Morning Executive Briefing ({0})").format(today)
            doc.for_user = user
            doc.type = "Alert"
            doc.email_content = ai_briefing
            doc.document_type = "AI Settings"
            doc.document_name = "AI Settings"
            doc.insert(ignore_permissions=True)

        frappe.db.commit()

    except Exception as e:
        frappe.log_error(title="Failed to generate Daily AI Briefing", message=str(e))
