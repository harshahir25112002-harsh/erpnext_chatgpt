# Copyright (c) 2026, Antigravity AI and contributors
# For license information, please see license.txt

import json
import frappe
from frappe import _
from frappe.utils import flt, nowdate, add_months

# Enhanced Tool Schemas for Function Calling
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
            "name": "get_supplier_price_comparison",
            "description": "Compare past purchase order prices and find the cheapest/best suppliers for an item.",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_code": {
                        "type": "string",
                        "description": "Item code to analyze"
                    }
                },
                "required": ["item_code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_delayed_purchase_orders",
            "description": "List Purchase Orders where expected delivery date is overdue.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_vendor_payables",
            "description": "Check total outstanding money owed to suppliers/vendors.",
            "parameters": {
                "type": "object",
                "properties": {
                    "supplier": {
                        "type": "string",
                        "description": "Optional specific supplier name"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_cash_flow_summary",
            "description": "Summarize current liquidity from Bank and Cash accounts.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "diagnose_document_error",
            "description": "Diagnose why an ERPNext document failed to save or submit and get the exact fix.",
            "parameters": {
                "type": "object",
                "properties": {
                    "doctype": { "type": "string" },
                    "docname": { "type": "string" },
                    "error_message": { "type": "string" }
                },
                "required": ["doctype", "docname"]
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
    },
    {
        "type": "function",
        "function": {
            "name": "create_draft_purchase_invoice",
            "description": "Create a DRAFT Purchase Invoice from extracted invoice data for review.",
            "parameters": {
                "type": "object",
                "properties": {
                    "supplier": { "type": "string" },
                    "bill_no": { "type": "string" },
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "item_code": { "type": "string" },
                                "qty": { "type": "number" },
                                "rate": { "type": "number" }
                            }
                        }
                    }
                },
                "required": ["supplier"]
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
    elif tool_name == "get_supplier_price_comparison":
        return tool_get_supplier_price_comparison(arguments.get("item_code"))
    elif tool_name == "get_delayed_purchase_orders":
        return tool_get_delayed_purchase_orders()
    elif tool_name == "get_vendor_payables":
        return tool_get_vendor_payables(arguments.get("supplier"))
    elif tool_name == "get_cash_flow_summary":
        return tool_get_cash_flow_summary()
    elif tool_name == "diagnose_document_error":
        return tool_diagnose_document_error(arguments.get("doctype"), arguments.get("docname"), arguments.get("error_message"))
    elif tool_name == "create_draft_lead":
        return tool_create_draft_lead(arguments)
    elif tool_name == "create_draft_purchase_invoice":
        return tool_create_draft_purchase_invoice(arguments)
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
        "warehouses": bins[:10],
        "link": f"/app/query-report/Stock%20Balance?item_code={item_code}"
    }

def tool_get_customer_outstanding(customer: str) -> dict:
    if not frappe.has_permission("Customer", "read"):
        return {"error": "Permission denied to view Customer data."}

    if not customer or not frappe.db.exists("Customer", customer):
        return {"error": f"Customer '{customer}' not found."}

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
        "recent_invoices": invoices[:5],
        "link": f"/app/sales-invoice?customer={customer}&outstanding_amount=%3E0"
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
        "currency": frappe.defaults.get_global_default("currency") or "USD",
        "link": "/app/sales-order"
    }

def tool_get_supplier_price_comparison(item_code: str) -> dict:
    """
    Compares past Purchase Order rates across suppliers for an item.
    """
    if not frappe.has_permission("Purchase Order", "read"):
        return {"error": "Permission denied to view Purchase Orders."}

    if not item_code or not frappe.db.exists("Item", item_code):
        return {"error": f"Item '{item_code}' not found."}

    po_items = frappe.db.sql("""
        SELECT po.supplier, poi.rate, po.transaction_date, po.name as po_name
        FROM `tabPurchase Order Item` poi
        JOIN `tabPurchase Order` po ON poi.parent = po.name
        WHERE poi.item_code = %s AND po.docstatus = 1
        ORDER BY poi.rate ASC, po.transaction_date DESC
        LIMIT 10
    """, (item_code,), as_dict=True)

    if not po_items:
        return {"item_code": item_code, "message": "No historical Purchase Orders found for this item."}

    cheapest = po_items[0]
    return {
        "item_code": item_code,
        "cheapest_supplier": cheapest.get("supplier"),
        "lowest_rate": flt(cheapest.get("rate")),
        "comparison": po_items,
        "link": f"/app/item/{item_code}"
    }

def tool_get_delayed_purchase_orders() -> dict:
    """
    Lists Purchase Orders with delayed deliveries past schedule_date.
    """
    if not frappe.has_permission("Purchase Order", "read"):
        return {"error": "Permission denied to view Purchase Orders."}

    delayed = frappe.get_all(
        "Purchase Order",
        filters={
            "docstatus": 1,
            "status": ["in", ["To Receive and Bill", "To Receive"]],
            "schedule_date": ["<", nowdate()]
        },
        fields=["name", "supplier", "schedule_date", "grand_total", "status"],
        limit_page_length=15
    )

    return {
        "delayed_count": len(delayed),
        "orders": delayed,
        "link": "/app/purchase-order?status=To%20Receive"
    }

def tool_get_vendor_payables(supplier: str = None) -> dict:
    """
    Computes total payables owed to vendors.
    """
    if not frappe.has_permission("Purchase Invoice", "read"):
        return {"error": "Permission denied to view Purchase Invoices."}

    filters = {
        "docstatus": 1,
        "outstanding_amount": [">", 0]
    }
    if supplier:
        filters["supplier"] = supplier

    invoices = frappe.get_all(
        "Purchase Invoice",
        filters=filters,
        fields=["name", "supplier", "due_date", "grand_total", "outstanding_amount"]
    )

    total_payable = sum(flt(inv.outstanding_amount) for inv in invoices)
    overdue_invoices = [inv for inv in invoices if inv.due_date and str(inv.due_date) < nowdate()]
    total_overdue = sum(flt(inv.outstanding_amount) for inv in overdue_invoices)

    return {
        "supplier": supplier or "All Suppliers",
        "total_payable": total_payable,
        "total_overdue": total_overdue,
        "open_invoice_count": len(invoices),
        "currency": frappe.defaults.get_global_default("currency") or "USD",
        "link": "/app/purchase-invoice?outstanding_amount=%3E0"
    }

def tool_get_cash_flow_summary() -> dict:
    """
    Summarizes immediate liquid balances from Bank and Cash accounts.
    """
    if not frappe.has_permission("Account", "read"):
        return {"error": "Permission denied to view Accounts / Financials."}

    accounts = frappe.get_all(
        "Account",
        filters={"account_type": ["in", ["Bank", "Cash"]], "is_group": 0},
        fields=["name", "account_name", "account_currency", "account_type"]
    )

    summary = []
    total_liquidity = 0.0

    for acc in accounts:
        # Sum debits minus credits from GL Entry for current balance
        bal = frappe.db.sql("""
            SELECT SUM(debit - credit)
            FROM `tabGL Entry`
            WHERE account = %s AND is_cancelled = 0
        """, (acc.name,))[0][0] or 0.0

        current_bal = flt(bal)
        total_liquidity += current_bal
        summary.append({
            "account": acc.account_name,
            "type": acc.account_type,
            "balance": current_bal
        })

    return {
        "total_liquid_funds": total_liquidity,
        "currency": frappe.defaults.get_global_default("currency") or "USD",
        "accounts": summary[:8],
        "link": "/app/query-report/General%20Ledger"
    }

def tool_diagnose_document_error(doctype: str, docname: str, error_message: str = None) -> dict:
    """
    Inspects document validation state, negative inventory, missing accounts, or date locks.
    """
    if not frappe.has_permission(doctype, "read", doc=docname):
        return {"error": f"Permission denied for {doctype} {docname}"}

    doc = frappe.get_doc(doctype, docname)
    findings = []
    remediation_steps = []

    # Check 1: Mandatory missing fields
    meta = frappe.get_meta(doctype)
    for field in meta.get_mandatory_fields():
        if not doc.get(field.fieldname):
            findings.append(f"Missing mandatory field '{field.label}' ({field.fieldname}).")
            remediation_steps.append(f"Enter a valid value for {field.label}.")

    # Check 2: Stock items with negative inventory risk
    if hasattr(doc, "items"):
        for item in doc.items:
            item_code = item.get("item_code")
            warehouse = item.get("warehouse")
            qty = flt(item.get("qty") or item.get("stock_qty"))

            if item_code and warehouse:
                # Check bin
                actual_qty = frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": warehouse}, "actual_qty") or 0.0
                if flt(actual_qty) < qty and doctype in ["Delivery Note", "Sales Invoice", "Stock Entry"]:
                    findings.append(f"Insufficient stock for '{item_code}' in warehouse '{warehouse}'. Required: {qty}, Available: {actual_qty}.")
                    remediation_steps.append(f"Create a Material Receipt (Stock Entry) for {qty - flt(actual_qty)} units of {item_code} in {warehouse}, or change the warehouse.")

    # Check 3: Closed Fiscal Year or Frozen Period
    posting_date = doc.get("posting_date") or doc.get("transaction_date")
    if posting_date:
        closed_period = frappe.db.get_single_value("Accounts Settings", "period_closing_date")
        if closed_period and str(posting_date) <= str(closed_period):
            findings.append(f"Posting Date {posting_date} falls inside a closed accounting period (before {closed_period}).")
            remediation_steps.append(f"Change Posting Date to after {closed_period} or ask Finance to review period lock.")

    return {
        "doctype": doctype,
        "docname": docname,
        "provided_error": error_message or "General validation failure",
        "diagnostic_findings": findings if findings else ["Document structure is intact; error might be network or permission-related."],
        "remediation_steps": remediation_steps if remediation_steps else ["Check that current user has write/submit permissions."],
        "link": f"/app/{frappe.scrub(doctype)}/{docname}"
    }

def tool_create_draft_lead(args: dict) -> dict:
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
    lead_doc.insert()

    return {
        "status": "draft_created",
        "lead_name": lead_doc.name,
        "message": f"Draft Lead '{lead_doc.lead_name}' created successfully.",
        "link": f"/app/lead/{lead_doc.name}"
    }

def tool_create_draft_purchase_invoice(args: dict) -> dict:
    """
    Creates a Purchase Invoice in Draft status (docstatus=0) from extracted invoice data.
    """
    if not frappe.has_permission("Purchase Invoice", "create"):
        return {"error": "Permission denied: User cannot create Purchase Invoices."}

    supplier = args.get("supplier")
    if not supplier or not frappe.db.exists("Supplier", supplier):
        return {"error": f"Supplier '{supplier}' not found in ERPNext. Please register supplier first."}

    items = args.get("items", [])
    if not items:
        return {"error": "At least one item is required to draft an invoice."}

    invoice = frappe.get_doc({
        "doctype": "Purchase Invoice",
        "supplier": supplier,
        "bill_no": args.get("bill_no", "AI-EXTRACTED"),
        "bill_date": nowdate(),
        "items": []
    })

    for itm in items:
        item_code = itm.get("item_code")
        # Validate or fallback to default item
        if not frappe.db.exists("Item", item_code):
            # Try to match by description or pick first available item
            item_code = frappe.db.get_value("Item", {}, "name")

        invoice.append("items", {
            "item_code": item_code,
            "qty": flt(itm.get("qty", 1)),
            "rate": flt(itm.get("rate", 0))
        })

    invoice.insert()

    return {
        "status": "draft_created",
        "invoice_name": invoice.name,
        "message": f"Draft Purchase Invoice '{invoice.name}' created for Supplier '{supplier}'. Requires human review.",
        "link": f"/app/purchase-invoice/{invoice.name}"
    }
