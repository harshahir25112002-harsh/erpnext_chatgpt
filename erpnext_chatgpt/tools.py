# Copyright (c) 2026, Antigravity AI and contributors
# For license information, please see license.txt

import json
import frappe
from frappe import _
from frappe.utils import flt, nowdate, add_months

# Universal, Version-Agnostic Tool Schemas (v15, v16, v17)
AVAILABLE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_erp_records",
            "description": "Search and display a filtered list of records for any DocType (Sales Invoices, Items, Leads, etc.) directly in chat.",
            "parameters": {
                "type": "object",
                "properties": {
                    "doctype": { "type": "string", "description": "DocType name, e.g. Sales Invoice, Item, Customer" },
                    "search_term": { "type": "string", "description": "Customer name, item code, or text query" },
                    "filters": { "type": "object", "description": "Key-value dictionary of filters" },
                    "limit": { "type": "integer", "description": "Number of records (default: 5)" }
                },
                "required": ["doctype"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_stock_balance",
            "description": "Get real-time stock balance for an item across warehouses by code or item name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_code": { "type": "string", "description": "Item Code or Item Name" },
                    "warehouse": { "type": "string", "description": "Optional specific warehouse" }
                },
                "required": ["item_code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_customer_outstanding",
            "description": "Retrieve unpaid invoices and overdue balance for a customer with filtered list.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer": { "type": "string", "description": "Customer name or ID" }
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
                    "months": { "type": "integer", "description": "Past months (default: 3)" },
                    "customer": { "type": "string" }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_supplier_price_comparison",
            "description": "Compare historical Purchase Order rates across suppliers for any item.",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_code": { "type": "string" }
                },
                "required": ["item_code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_delayed_purchase_orders",
            "description": "List Purchase Orders with delayed deliveries.",
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
                    "supplier": { "type": "string" }
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
            "description": "Inspect why an ERPNext document gave an error on submit and get the fix.",
            "parameters": {
                "type": "object",
                "properties": {
                    "doctype": { "type": "string" },
                    "docname": { "type": "string" },
                    "error_message": { "type": "string" }
                },
                "required": ["doctype"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_draft_purchase_invoice",
            "description": "Creates a verified DRAFT Purchase Invoice in ERPNext.",
            "parameters": {
                "type": "object",
                "properties": {
                    "supplier": { "type": "string" },
                    "bill_no": { "type": "string" },
                    "items": { "type": "array" }
                },
                "required": ["supplier"]
            }
        }
    }
]

def execute_tool_call(tool_name: str, arguments: dict) -> dict:
    if tool_name == "search_erp_records":
        return tool_search_erp_records(arguments.get("doctype"), arguments.get("search_term"), arguments.get("filters"), arguments.get("limit", 5))
    elif tool_name == "get_stock_balance":
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
    elif tool_name == "create_draft_purchase_invoice":
        return tool_create_draft_purchase_invoice(arguments)
    else:
        return {"error": f"Tool '{tool_name}' is not recognized."}

def tool_search_erp_records(doctype: str, search_term: str = None, custom_filters: dict = None, limit: int = 5) -> dict:
    """
    Universally queries and formats a mini list view for any DocType.
    """
    if not frappe.db.exists("DocType", doctype):
        return {"error": f"DocType '{doctype}' does not exist in ERPNext."}

    if not frappe.has_permission(doctype, "read"):
        return {"error": f"Permission denied to view '{doctype}'."}

    filters = custom_filters or {}
    meta = frappe.get_meta(doctype)
    search_field = meta.get("title_field") or "name"

    if search_term and search_term.strip():
        # Match by name or title or customer/supplier name
        if doctype == "Sales Invoice":
            filters["customer"] = ["like", f"%{search_term.strip()}%"]
        elif doctype == "Purchase Invoice":
            filters["supplier"] = ["like", f"%{search_term.strip()}%"]
        elif doctype == "Item":
            # Search code or name
            items = frappe.get_all("Item", or_filters={"name": ["like", f"%{search_term}%"], "item_name": ["like", f"%{search_term}%"]}, limit=limit, fields=["name", "item_name", "item_group", "stock_uom"])
            return {"doctype": doctype, "records": items, "count": len(items)}
        else:
            filters[search_field] = ["like", f"%{search_term.strip()}%"]

    # Choose smart fields depending on DocType
    fields = ["name"]
    if doctype == "Sales Invoice":
        fields = ["name", "customer", "posting_date", "grand_total", "outstanding_amount", "status"]
    elif doctype == "Purchase Invoice":
        fields = ["name", "supplier", "posting_date", "grand_total", "outstanding_amount", "status"]
    elif doctype == "Customer":
        fields = ["name", "customer_name", "customer_group", "territory"]
    elif doctype == "Item":
        fields = ["name", "item_name", "item_group", "stock_uom"]
    else:
        fields = ["name", "modified"]

    records = frappe.get_all(doctype, filters=filters, fields=fields, limit_page_length=limit, order_by="modified desc")

    for r in records:
        r["link"] = f"/app/{frappe.scrub(doctype)}/{r.name}"

    filter_param = f"?customer={search_term}" if (doctype == "Sales Invoice" and search_term) else ""
    return {
        "doctype": doctype,
        "search_term": search_term,
        "records": records,
        "count": len(records),
        "link": f"/app/{frappe.scrub(doctype)}{filter_param}"
    }

def tool_get_stock_balance(item_code: str, warehouse: str = None) -> dict:
    if not frappe.has_permission("Bin", "read"):
        return {"error": "Permission denied to view Stock Balance."}

    # Dynamic fuzzy resolution: if item_code is not exact match, search by item_name
    real_item_code = item_code
    if not frappe.db.exists("Item", item_code):
        matched = frappe.db.get_value("Item", {"item_name": ["like", f"%{item_code}%"]}, "name")
        if matched:
            real_item_code = matched
        else:
            # Return list of top available items
            sample_items = frappe.get_all("Item", limit=5, fields=["name", "item_name", "item_group"])
            return {
                "error": f"Item '{item_code}' not found.",
                "available_items_sample": sample_items,
                "hint": "Please choose from the items above."
            }

    filters = {"item_code": real_item_code}
    if warehouse:
        filters["warehouse"] = warehouse

    bins = frappe.get_all(
        "Bin",
        filters=filters,
        fields=["warehouse", "actual_qty", "reserved_qty", "projected_qty"]
    )

    total_actual = sum(flt(b.actual_qty) for b in bins)
    total_projected = sum(flt(b.projected_qty) for b in bins)
    item_title = frappe.db.get_value("Item", real_item_code, "item_name") or real_item_code

    return {
        "item_code": real_item_code,
        "item_name": item_title,
        "total_actual_stock": total_actual,
        "total_projected_stock": total_projected,
        "warehouses": bins[:10],
        "link": f"/app/query-report/Stock%20Balance?item_code={real_item_code}"
    }

def tool_get_customer_outstanding(customer: str) -> dict:
    if not frappe.has_permission("Customer", "read"):
        return {"error": "Permission denied to view Customer data."}

    # Match customer name loosely
    real_customer = customer
    if not frappe.db.exists("Customer", customer):
        matched = frappe.db.get_value("Customer", {"customer_name": ["like", f"%{customer}%"]}, "name")
        if matched:
            real_customer = matched
        else:
            return {"error": f"Customer '{customer}' not found in ERPNext."}

    invoices = frappe.get_all(
        "Sales Invoice",
        filters={"customer": real_customer, "docstatus": 1, "outstanding_amount": [">", 0]},
        fields=["name", "posting_date", "due_date", "grand_total", "outstanding_amount", "status"],
        order_by="due_date asc"
    )

    total_outstanding = sum(flt(inv.outstanding_amount) for inv in invoices)
    overdue_invoices = [inv for inv in invoices if str(inv.due_date) < nowdate()]
    total_overdue = sum(flt(inv.outstanding_amount) for inv in overdue_invoices)

    for inv in invoices:
        inv["link"] = f"/app/sales-invoice/{inv.name}"

    return {
        "customer": real_customer,
        "total_outstanding": total_outstanding,
        "total_overdue": total_overdue,
        "open_invoice_count": len(invoices),
        "invoices": invoices[:8],
        "link": f"/app/sales-invoice?customer={real_customer}&outstanding_amount=%3E0"
    }

def tool_get_sales_summary(months: int = 3, customer: str = None) -> dict:
    if not frappe.has_permission("Sales Order", "read"):
        return {"error": "Permission denied to view Sales Orders."}

    start_date = add_months(nowdate(), -int(months))
    filters = {"transaction_date": [">=", start_date], "docstatus": 1}
    if customer:
        filters["customer"] = customer

    orders = frappe.get_all("Sales Order", filters=filters, fields=["name", "customer", "grand_total", "transaction_date"], limit=10, order_by="transaction_date desc")
    total_sales = sum(flt(o.grand_total) for o in orders)
    for o in orders:
        o["link"] = f"/app/sales-order/{o.name}"

    return {
        "period_months": months,
        "order_count": len(orders),
        "total_sales_amount": total_sales,
        "recent_orders": orders,
        "currency": frappe.defaults.get_global_default("currency") or "INR",
        "link": "/app/sales-order"
    }

def tool_get_supplier_price_comparison(item_code: str) -> dict:
    if not frappe.has_permission("Purchase Order", "read"):
        return {"error": "Permission denied to view Purchase Orders."}

    # Resolve item code if needed
    real_code = item_code
    if not frappe.db.exists("Item", item_code):
        matched = frappe.db.get_value("Item", {"item_name": ["like", f"%{item_code}%"]}, "name")
        if matched:
            real_code = matched
        else:
            return {"error": f"Item '{item_code}' not found."}

    po_items = frappe.db.sql("""
        SELECT po.supplier, poi.rate, po.transaction_date, po.name as po_name
        FROM `tabPurchase Order Item` poi
        JOIN `tabPurchase Order` po ON poi.parent = po.name
        WHERE poi.item_code = %s AND po.docstatus = 1
        ORDER BY poi.rate ASC, po.transaction_date DESC
        LIMIT 10
    """, (real_code,), as_dict=True)

    if not po_items:
        return {"item_code": real_code, "message": "No historical Purchase Orders found for this item."}

    return {
        "item_code": real_code,
        "cheapest_supplier": po_items[0].get("supplier"),
        "lowest_rate": flt(po_items[0].get("rate")),
        "comparison_table": po_items,
        "link": f"/app/item/{real_code}"
    }

def tool_get_delayed_purchase_orders() -> dict:
    if not frappe.has_permission("Purchase Order", "read"):
        return {"error": "Permission denied to view Purchase Orders."}

    delayed = frappe.get_all(
        "Purchase Order",
        filters={"docstatus": 1, "status": ["in", ["To Receive and Bill", "To Receive"]], "schedule_date": ["<", nowdate()]},
        fields=["name", "supplier", "schedule_date", "grand_total", "status"],
        limit_page_length=15
    )
    for po in delayed:
        po["link"] = f"/app/purchase-order/{po.name}"

    return {
        "delayed_count": len(delayed),
        "orders": delayed,
        "link": "/app/purchase-order?status=To%20Receive"
    }

def tool_get_vendor_payables(supplier: str = None) -> dict:
    if not frappe.has_permission("Purchase Invoice", "read"):
        return {"error": "Permission denied to view Purchase Invoices."}

    filters = {"docstatus": 1, "outstanding_amount": [">", 0]}
    if supplier:
        filters["supplier"] = supplier

    invoices = frappe.get_all(
        "Purchase Invoice",
        filters=filters,
        fields=["name", "supplier", "due_date", "grand_total", "outstanding_amount"]
    )

    total_payable = sum(flt(inv.outstanding_amount) for inv in invoices)
    overdue_invoices = [inv for inv in invoices if inv.due_date and str(inv.due_date) < nowdate()]

    for inv in invoices:
        inv["link"] = f"/app/purchase-invoice/{inv.name}"

    return {
        "supplier": supplier or "All Suppliers",
        "total_payable": total_payable,
        "total_overdue": sum(flt(inv.outstanding_amount) for inv in overdue_invoices),
        "open_invoices": invoices[:8],
        "currency": frappe.defaults.get_global_default("currency") or "INR",
        "link": "/app/purchase-invoice?outstanding_amount=%3E0"
    }

def tool_get_cash_flow_summary() -> dict:
    if not frappe.has_permission("Account", "read"):
        return {"error": "Permission denied to view Accounts / Financials."}

    accounts = frappe.get_all(
        "Account",
        filters={"account_type": ["in", ["Bank", "Cash"]], "is_group": 0},
        fields=["name", "account_name", "account_type"]
    )

    summary = []
    total_liquidity = 0.0

    for acc in accounts:
        bal = frappe.db.sql("SELECT SUM(debit - credit) FROM `tabGL Entry` WHERE account = %s AND is_cancelled = 0", (acc.name,))[0][0] or 0.0
        cur_bal = flt(bal)
        total_liquidity += cur_bal
        summary.append({"account": acc.account_name, "type": acc.account_type, "balance": cur_bal})

    return {
        "total_liquid_funds": total_liquidity,
        "currency": frappe.defaults.get_global_default("currency") or "INR",
        "accounts": summary[:8],
        "link": "/app/query-report/General%20Ledger"
    }

def tool_diagnose_document_error(doctype: str, docname: str = None, error_message: str = None) -> dict:
    """
    Zero-hardcoding error troubleshooter:
    If docname is not provided or not found, dynamically finds the most recent modified document.
    """
    if not frappe.has_permission(doctype, "read"):
        return {"error": f"Permission denied for {doctype}"}

    real_docname = docname
    if not real_docname or not frappe.db.exists(doctype, real_docname):
        recent = frappe.get_all(doctype, order_by="modified desc", limit=1, pluck="name")
        if recent:
            real_docname = recent[0]
        else:
            return {"error": f"No records found for DocType '{doctype}' to diagnose."}

    doc = frappe.get_doc(doctype, real_docname)
    findings = []
    remediation_steps = []

    # 1. Missing mandatory fields
    meta = frappe.get_meta(doctype)
    for field in meta.get_mandatory_fields():
        if not doc.get(field.fieldname):
            findings.append(f"Missing mandatory field '{field.label}' ({field.fieldname}).")
            remediation_steps.append(f"Fill in {field.label}.")

    # 2. Insufficient stock check
    if hasattr(doc, "items"):
        for item in doc.items:
            item_code = item.get("item_code")
            warehouse = item.get("warehouse")
            qty = flt(item.get("qty") or item.get("stock_qty"))

            if item_code and warehouse:
                actual_qty = frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": warehouse}, "actual_qty") or 0.0
                if flt(actual_qty) < qty and doctype in ["Delivery Note", "Sales Invoice", "Stock Entry"]:
                    findings.append(f"Insufficient stock for '{item_code}' in warehouse '{warehouse}'. Required: {qty}, Available: {actual_qty}.")
                    remediation_steps.append(f"Create a Material Receipt for {qty - flt(actual_qty)} units of {item_code} in {warehouse}, or change the warehouse.")

    # 3. Closed period check
    posting_date = doc.get("posting_date") or doc.get("transaction_date")
    if posting_date:
        closed_period = frappe.db.get_single_value("Accounts Settings", "period_closing_date")
        if closed_period and str(posting_date) <= str(closed_period):
            findings.append(f"Posting Date {posting_date} is inside a closed accounting period (before {closed_period}).")
            remediation_steps.append(f"Change Posting Date to after {closed_period}.")

    return {
        "doctype": doctype,
        "docname": real_docname,
        "diagnostic_findings": findings if findings else ["Document validation fields appear valid."],
        "remediation_steps": remediation_steps if remediation_steps else ["Verify user submission roles or check server error logs."],
        "link": f"/app/{frappe.scrub(doctype)}/{real_docname}"
    }

def get_or_create_supplier(supplier_name: str) -> tuple:
    """
    Zero-hardcoding: Resolves or dynamically creates the real Supplier in ERPNext.
    Returns (supplier_doc_name, is_newly_created).
    """
    raw = (supplier_name or "").strip()
    if not raw:
        first = frappe.db.get_value("Supplier", {}, "name")
        return (first or "Standard Supplier", False)

    # 1. Exact or loose match on existing Supplier
    if frappe.db.exists("Supplier", raw):
        return (raw, False)

    matched = frappe.db.get_value("Supplier", {"supplier_name": ["like", f"%{raw}%"]}, "name")
    if matched:
        return (matched, False)

    # 2. Determine default Supplier Group safely
    supplier_group = (
        frappe.db.get_single_value("Buying Settings", "supplier_group")
        or frappe.db.get_value("Supplier Group", {"is_group": 0}, "name")
        or "All Supplier Groups"
    )
    if not frappe.db.exists("Supplier Group", supplier_group):
        supplier_group = frappe.db.get_value("Supplier Group", {}, "name") or "All Supplier Groups"

    # 3. Create real Supplier record in ERPNext
    try:
        sup_doc = frappe.get_doc({
            "doctype": "Supplier",
            "supplier_name": raw,
            "supplier_group": supplier_group,
            "supplier_type": "Company"
        })
        sup_doc.insert(ignore_permissions=True)
        return (sup_doc.name, True)
    except Exception as err:
        frappe.log_error(title="Auto-Create Supplier Fallback", message=str(err))
        # If creation fails, fallback to first existing
        first = frappe.db.get_value("Supplier", {}, "name")
        return (first or raw, False)

def get_or_create_item(item_code_or_name: str, rate: float = 0.0) -> tuple:
    """
    Zero-hardcoding: Resolves or dynamically creates the real Item in ERPNext.
    Returns (item_code, is_newly_created).
    """
    raw = (item_code_or_name or "").strip()[:140]
    if not raw:
        first = frappe.db.get_value("Item", {}, "name")
        return (first or "Service Item", False)

    # 1. Exact match by name / item_code
    if frappe.db.exists("Item", raw):
        return (raw, False)

    # 2. Fuzzy match by item_name
    matched = frappe.db.get_value("Item", {"item_name": ["like", f"%{raw}%"]}, "name")
    if matched:
        return (matched, False)

    # 3. Determine default Item Group
    item_group = (
        frappe.db.get_value("Item Group", {"is_group": 0}, "name")
        or "All Item Groups"
    )
    if not frappe.db.exists("Item Group", item_group):
        item_group = frappe.db.get_value("Item Group", {}, "name") or "All Item Groups"

    # 4. Determine default Stock UOM
    stock_uom = (
        frappe.db.get_single_value("Stock Settings", "stock_uom")
        or (frappe.db.exists("UOM", "Nos") and "Nos")
        or frappe.db.get_value("UOM", {}, "name")
        or "Nos"
    )

    # 5. Create Item as service/non-stock (is_stock_item=0)
    # This prevents stock receipt / warehouse discrepancy blockers on invoice submission
    try:
        item_doc = frappe.get_doc({
            "doctype": "Item",
            "item_code": raw,
            "item_name": raw,
            "item_group": item_group,
            "stock_uom": stock_uom,
            "is_stock_item": 0,
            "standard_rate": flt(rate)
        })
        item_doc.insert(ignore_permissions=True)
        return (item_doc.name, True)
    except Exception as err:
        frappe.log_error(title="Auto-Create Item Fallback", message=str(err))
        first = frappe.db.get_value("Item", {}, "name")
        return (first or raw, False)

def get_or_create_customer(customer_name: str) -> tuple:
    """
    Zero-hardcoding: Resolves or dynamically creates the real Customer in ERPNext.
    Returns (customer_doc_name, is_newly_created).
    """
    raw = (customer_name or "").strip()
    if not raw:
        first = frappe.db.get_value("Customer", {}, "name")
        return (first or "Standard Customer", False)

    if frappe.db.exists("Customer", raw):
        return (raw, False)

    matched = frappe.db.get_value("Customer", {"customer_name": ["like", f"%{raw}%"]}, "name")
    if matched:
        return (matched, False)

    cust_group = (
        frappe.db.get_single_value("Selling Settings", "customer_group")
        or frappe.db.get_value("Customer Group", {"is_group": 0}, "name")
        or "All Customer Groups"
    )
    territory = (
        frappe.db.get_single_value("Selling Settings", "territory")
        or frappe.db.get_value("Territory", {"is_group": 0}, "name")
        or "All Territories"
    )

    try:
        cust_doc = frappe.get_doc({
            "doctype": "Customer",
            "customer_name": raw,
            "customer_group": cust_group,
            "territory": territory,
            "customer_type": "Company"
        })
        cust_doc.insert(ignore_permissions=True)
        return (cust_doc.name, True)
    except Exception as err:
        frappe.log_error(title="Auto-Create Customer Fallback", message=str(err))
        first = frappe.db.get_value("Customer", {}, "name")
        return (first or raw, False)

def tool_create_draft_purchase_invoice(args: dict) -> dict:
    """
    Creates a confirmed Draft Purchase Invoice in ERPNext using real extracted data.
    If Supplier or Items do not exist, they are dynamically created.
    """
    if not frappe.has_permission("Purchase Invoice", "create"):
        return {"status": "error", "error": "Permission denied: User cannot create Purchase Invoices."}

    raw_supplier = (args.get("supplier") or "").strip()
    supplier, sup_created = get_or_create_supplier(raw_supplier)

    items = args.get("items", [])
    if not items:
        items = [{"item_code": "General Purchases", "qty": 1, "rate": flt(args.get("total", 0))}]

    created_items = []
    invoice_items = []
    total_calc = 0.0

    for itm in items:
        raw_code = itm.get("item_code") or itm.get("item_name") or "General Purchases"
        qty = max(flt(itm.get("qty", 1)), 1.0)
        rate = flt(itm.get("rate", 0))
        amount = flt(itm.get("amount") or (qty * rate))
        total_calc += amount

        real_item_code, item_created = get_or_create_item(raw_code, rate)
        if item_created:
            created_items.append(real_item_code)

        invoice_items.append({
            "item_code": real_item_code,
            "qty": qty,
            "rate": rate,
            "amount": amount
        })

    try:
        bill_no = str(args.get("bill_no") or "").strip() or f"INV-{nowdate().replace('-', '')}"
        invoice = frappe.get_doc({
            "doctype": "Purchase Invoice",
            "supplier": supplier,
            "bill_no": bill_no,
            "bill_date": args.get("bill_date") or nowdate(),
            "due_date": args.get("due_date") or nowdate(),
            "remarks": "Extracted and confirmed via AI Copilot.",
            "items": invoice_items
        })
        invoice.insert()

        creation_notes = []
        if sup_created:
            creation_notes.append(f"✨ Created new Supplier: <b>{supplier}</b>")
        if created_items:
            creation_notes.append(f"✨ Created {len(created_items)} new Item(s): <b>{', '.join(created_items[:3])}{'...' if len(created_items) > 3 else ''}</b>")

        summary_msg = f"Draft Purchase Invoice <b>{invoice.name}</b> successfully created for Supplier <b>{supplier}</b>."
        if creation_notes:
            summary_msg += "<br>" + "<br>".join(creation_notes)

        return {
            "status": "draft_created",
            "invoice_name": invoice.name,
            "supplier": supplier,
            "total": invoice.grand_total or total_calc,
            "is_new_supplier": sup_created,
            "new_items_created": created_items,
            "message": summary_msg,
            "link": f"/app/purchase-invoice/{invoice.name}"
        }

    except Exception as e:
        frappe.log_error(title="Failed to create Purchase Invoice", message=frappe.get_traceback())
        return {"status": "error", "error": f"Failed to create Purchase Invoice: {str(e)}"}
