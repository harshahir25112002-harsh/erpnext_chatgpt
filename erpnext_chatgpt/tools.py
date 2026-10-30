# Copyright (c) 2026, Antigravity AI and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, nowdate, add_months

# Tool Schemas for Function Calling
AVAILABLE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_stock_balance",
            "description": "Get current available stock balance for an item across warehouses.",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_code": {
                        "type": "string",
                        "description": "The exact item code (e.g., ITEM-001)"
                    },
                    "warehouse": {
                        "type": "string",
                        "description": "Optional specific warehouse name"
                    }
                },
                "required": ["item_code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_customer_outstanding",
            "description": "Retrieve total outstanding balance and overdue amount for a customer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer": {
                        "type": "string",
                        "description": "Customer name or ID"
                    }
                },
                "required": ["customer"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_sales_summary",
            "description": "Summarize total sales amount and order count for recent months.",
            "parameters": {
                "type": "object",
                "properties": {
                    "months": {
                        "type": "integer",
                        "description": "Number of past months to summarize (default: 3)"
                    },
                    "customer": {
                        "type": "string",
                        "description": "Optional customer name to filter by"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_draft_lead",
            "description": "Create a DRAFT lead in CRM for human review. Never auto-commits or submits.",
            "parameters": {
                "type": "object",
                "properties": {
                    "lead_name": { "type": "string" },
                    "email_id": { "type": "string" },
                    "mobile_no": { "type": "string" },
                    "notes": { "type": "string" }
                },
                "required": ["lead_name"]
            }
        }
    }
]

def execute_tool_call(tool_name: str, arguments: dict) -> dict:
    """
    Validates arguments and executes strictly authorized tool calls.
    Never executes arbitrary SQL. Enforces Frappe permission checks.
    """
    if tool_name == "get_stock_balance":
        return tool_get_stock_balance(arguments.get("item_code"), arguments.get("warehouse"))
    elif tool_name == "get_customer_outstanding":
        return tool_get_customer_outstanding(arguments.get("customer"))
    elif tool_name == "get_sales_summary":
        return tool_get_sales_summary(arguments.get("months", 3), arguments.get("customer"))
    elif tool_name == "create_draft_lead":
        return tool_create_draft_lead(arguments)
    else:
        return {"error": f"Tool '{tool_name}' is not recognized or permitted."}

def tool_get_stock_balance(item_code: str, warehouse: str = None) -> dict:
    if not frappe.has_permission("Bin", "read"):
        return {"error": "Permission denied to view Stock Balance."}

    if not item_code or not frappe.db.exists("Item", item_code):
        return {"error": f"Item '{item_code}' not found."}

    filters = {"item_code": item_code}
    if warehouse:
        filters["warehouse"] = warehouse

    bins = frappe.get_all(
        "Bin",
        filters=filters,
        fields=["warehouse", "actual_qty", "reserved_qty", "projected_qty"]
    )

    total_actual = sum(flt(b.actual_qty) for b in bins)
    total_projected = sum(flt(b.projected_qty) for b in bins)

    return {
        "item_code": item_code,
        "total_actual_stock": total_actual,
        "total_projected_stock": total_projected,
        "warehouses": bins[:10]  # Cap results for safety
    }

def tool_get_customer_outstanding(customer: str) -> dict:
    if not frappe.has_permission("Customer", "read"):
        return {"error": "Permission denied to view Customer data."}

    if not customer or not frappe.db.exists("Customer", customer):
        return {"error": f"Customer '{customer}' not found."}

    # Query Sales Invoices with outstanding amount using Frappe ORM
    invoices = frappe.get_all(
        "Sales Invoice",
        filters={
            "customer": customer,
            "docstatus": 1,
            "outstanding_amount": [">", 0]
        },
        fields=["name", "posting_date", "due_date", "grand_total", "outstanding_amount"]
    )

    total_outstanding = sum(flt(inv.outstanding_amount) for inv in invoices)
    overdue_invoices = [inv for inv in invoices if str(inv.due_date) < nowdate()]
    total_overdue = sum(flt(inv.outstanding_amount) for inv in overdue_invoices)

    return {
        "customer": customer,
        "total_outstanding": total_outstanding,
        "total_overdue": total_overdue,
        "open_invoice_count": len(invoices),
        "recent_invoices": invoices[:5]
    }

def tool_get_sales_summary(months: int = 3, customer: str = None) -> dict:
    if not frappe.has_permission("Sales Order", "read"):
        return {"error": "Permission denied to view Sales Orders."}

    start_date = add_months(nowdate(), -int(months))
    filters = {
        "transaction_date": [">=", start_date],
        "docstatus": 1
    }
    if customer:
        filters["customer"] = customer

    orders = frappe.get_all(
        "Sales Order",
        filters=filters,
        fields=["name", "grand_total", "transaction_date"]
    )

    total_sales = sum(flt(o.grand_total) for o in orders)

    return {
        "period_months": months,
        "order_count": len(orders),
        "total_sales_amount": total_sales,
        "currency": frappe.defaults.get_global_default("currency") or "USD"
    }

def tool_create_draft_lead(args: dict) -> dict:
    """
    Creates a lead STRICTLY in draft/open status (docstatus=0).
    Requires explicit user permission to create Lead.
    """
    if not frappe.has_permission("Lead", "create"):
        return {"error": "Permission denied: User cannot create Leads."}

    lead_doc = frappe.get_doc({
        "doctype": "Lead",
        "lead_name": args.get("lead_name"),
        "email_id": args.get("email_id"),
        "mobile_no": args.get("mobile_no"),
        "notes": f"Created via AI Copilot.\n{args.get('notes', '')}",
        "status": "Lead"
    })
    # Normal insert (docstatus=0 by default in Frappe)
    lead_doc.insert()

    return {
        "status": "draft_created",
        "lead_name": lead_doc.name,
        "message": f"Draft Lead '{lead_doc.lead_name}' created successfully. Requires human confirmation."
    }

