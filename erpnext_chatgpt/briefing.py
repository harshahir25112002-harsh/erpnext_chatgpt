# Copyright (c) 2026, Antigravity AI and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, nowdate
from erpnext_chatgpt.providers import execute_chat_completion

def generate_briefing_content():
    """
    Synthesizes current ERP operational metrics into a clean executive morning summary
    strictly focused on TODAY's dues and actionable overdue items.
    """
    today = nowdate()
    currency = frappe.defaults.get_global_default("currency") or "INR"

    # 1. Customer Receivables: Due Today vs Past Overdue
    due_today_rec = frappe.db.sql("""
        SELECT SUM(outstanding_amount) as total, COUNT(name) as count
        FROM `tabSales Invoice`
        WHERE docstatus = 1 AND outstanding_amount > 0 AND due_date = %s
    """, (today,), as_dict=True)[0]
    rec_today_amt = flt(due_today_rec.get("total") or 0.0)
    rec_today_cnt = due_today_rec.get("count") or 0

    past_overdue_rec = frappe.db.sql("""
        SELECT SUM(outstanding_amount) as total, COUNT(name) as count
        FROM `tabSales Invoice`
        WHERE docstatus = 1 AND outstanding_amount > 0 AND due_date < %s
    """, (today,), as_dict=True)[0]
    rec_overdue_amt = flt(past_overdue_rec.get("total") or 0.0)
    rec_overdue_cnt = past_overdue_rec.get("count") or 0

    # 2. Vendor Payables: Due Today vs Past Overdue
    due_today_pay = frappe.db.sql("""
        SELECT SUM(outstanding_amount) as total, COUNT(name) as count
        FROM `tabPurchase Invoice`
        WHERE docstatus = 1 AND outstanding_amount > 0 AND due_date = %s
    """, (today,), as_dict=True)[0]
    pay_today_amt = flt(due_today_pay.get("total") or 0.0)
    pay_today_cnt = due_today_pay.get("count") or 0

    past_overdue_pay = frappe.db.sql("""
        SELECT SUM(outstanding_amount) as total, COUNT(name) as count
        FROM `tabPurchase Invoice`
        WHERE docstatus = 1 AND outstanding_amount > 0 AND due_date < %s
    """, (today,), as_dict=True)[0]
    pay_overdue_amt = flt(past_overdue_pay.get("total") or 0.0)
    pay_overdue_cnt = past_overdue_pay.get("count") or 0

    # 3. Delayed Purchase Orders (due on or before today)
    pos_due_today = frappe.db.count("Purchase Order", filters={
        "docstatus": 1,
        "status": ["in", ["To Receive and Bill", "To Receive"]],
        "schedule_date": today
    })
    pos_delayed_past = frappe.db.count("Purchase Order", filters={
        "docstatus": 1,
        "status": ["in", ["To Receive and Bill", "To Receive"]],
        "schedule_date": ["<", today]
    })

    # 4. Critical Support Issues
    urgent_issues = frappe.db.count("Issue", filters={
        "status": "Open",
        "priority": ["in", ["High", "Urgent"]]
    }) if frappe.db.exists("DocType", "Issue") else 0

    prompt = (
        f"You are an executive Chief of Staff preparing the Daily Executive Briefing for {today}.\n"
        "STRICT INSTRUCTIONS:\n"
        "1. Focus specifically on TODAY's actionable dues and overdue items.\n"
        "2. If an area has dues or overdue amounts, report: amount due today, total overdue, and use the exact pre-filtered markdown link provided below.\n"
        "3. If an area has 0 dues (zero invoices or zero delayed orders), write: '✅ All payments/orders up to date for today' and DO NOT include any links.\n"
        "4. DO NOT make up generic advice or report on categories that have no pending action.\n"
        "5. Keep the briefing under 120 words, structured as clean bullet points.\n\n"
        f"OPERATIONAL DATA FOR {today}:\n"
        f"- Receivables Due Today: {currency} {rec_today_amt:,.2f} ({rec_today_cnt} invoices) -> Link: [Invoices Due Today](/app/sales-invoice?outstanding_amount=>0&due_date={today})\n"
        f"- Receivables Overdue: {currency} {rec_overdue_amt:,.2f} ({rec_overdue_cnt} invoices) -> Link: [Review Overdue Receivables](/app/sales-invoice?outstanding_amount=>0&due_date=<={today})\n"
        f"- Payables Due Today: {currency} {pay_today_amt:,.2f} ({pay_today_cnt} invoices) -> Link: [Payables Due Today](/app/purchase-invoice?outstanding_amount=>0&due_date={today})\n"
        f"- Payables Overdue: {currency} {pay_overdue_amt:,.2f} ({pay_overdue_cnt} invoices) -> Link: [Review Overdue Payables](/app/purchase-invoice?outstanding_amount=>0&due_date=<={today})\n"
        f"- Delayed Purchase Orders: {pos_delayed_past + pos_due_today} orders -> Link: [View Delayed POs](/app/purchase-order?status=To%20Receive&schedule_date=<={today})\n"
        f"- Urgent Support Issues: {urgent_issues}\n"
    )

    messages = [
        {"role": "system", "content": "You are a concise executive advisor for ERPNext leadership."},
        {"role": "user", "content": prompt}
    ]
    res = execute_chat_completion(messages, model_override=None)
    return res.get("content", "Executive briefing generated.")

def send_daily_executive_briefing():
    """
    Automated daily 9:00 AM Cron Task.
    """
    settings = frappe.get_single("AI Settings")
    if not settings.enabled or settings.site_disabled:
        return

    today = nowdate()
    try:
        ai_briefing = generate_briefing_content()

        recipients = frappe.get_all(
            "Has Role",
            filters={"role": "System Manager", "parenttype": "User"},
            pluck="parent"
        )
        active_recipients = frappe.get_all(
            "User",
            filters={"name": ["in", list(set(recipients))], "enabled": 1},
            pluck="name"
        )

        for user in active_recipients:
            doc = frappe.new_doc("Notification Log")
            doc.subject = _("🌅 AI Morning Briefing ({0})").format(today)
            doc.for_user = user
            doc.type = "Alert"
            doc.email_content = ai_briefing
            # Open directly in AI Copilot page instead of AI Settings
            doc.document_type = "Page"
            doc.document_name = "chatgpt_copilot"
            doc.insert(ignore_permissions=True)

        frappe.db.commit()

    except Exception as e:
        frappe.log_error(title="Failed to generate Daily AI Briefing", message=str(e))
