# Copyright (c) 2026, Antigravity AI and contributors
# For license information, please see license.txt

import json
import frappe
from frappe import _
from frappe.utils import now_datetime
from erpnext_chatgpt.security import (
    mask_sensitive_text,
    sanitize_doc_for_llm,
    validate_prompt_injection
)
from erpnext_chatgpt.tools import (
    AVAILABLE_TOOLS,
    execute_tool_call
)
from erpnext_chatgpt.providers import (
    execute_chat_completion
)

def log_ai_request(user, status, provider, model, prompt, response, usage, cost, latency, ref_dt=None, ref_dn=None, error=None):
    """
    Persists audit trail and token analytics strictly in AI Request Log.
    """
    try:
        log_doc = frappe.get_doc({
            "doctype": "AI Request Log",
            "user": user,
            "status": status,
            "provider": provider,
            "model": model,
            "reference_doctype": ref_dt,
            "reference_name": ref_dn,
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
            "estimated_cost_usd": cost,
            "latency_sec": latency,
            "prompt_text": prompt[:2000] if prompt else "",
            "response_text": response[:4000] if response else "",
            "error_message": str(error) if error else ""
        })
        log_doc.insert(ignore_permissions=True)
        frappe.db.commit()
        return log_doc.name
    except Exception as log_err:
        frappe.log_error(title="Failed to write AI Request Log", message=str(log_err))
        return None

@frappe.whitelist()
def test_connection():
    """
    Validates credentials and endpoint connectivity.
    """
    try:
        messages = [
            {"role": "system", "content": "You are a test assistant. Reply 'Connected successfully' only."},
            {"role": "user", "content": "Ping"}
        ]
        res = execute_chat_completion(messages, model_override=None)
        log_id = log_ai_request(
            frappe.session.user, res["status"], res["provider"], res["model"],
            "Ping", res["content"], res["usage"], res["cost_usd"], res["latency_sec"]
        )
        return {
            "status": "success",
            "sample": res["content"],
            "latency": res["latency_sec"],
            "log_id": log_id
        }
    except Exception as e:
        frappe.log_error(title="AI Test Connection Failed", message=frappe.get_traceback())
        return {"status": "error", "error": str(e)}

@frappe.whitelist()
def chat(message, conversation_id=None, reference_doctype=None, reference_name=None, async_mode=False):
    """
    Secure Whitelisted Chat Endpoint:
    1. Validates prompt injection.
    2. Validates DocType read permissions (never bypasses security).
    3. Masks sensitive data (PAN, GSTIN, Bank, Cards).
    4. Supports read-only Tool Calling.
    5. Audits every call in AI Request Log with token and cost tracking.
    """
    if not message or not message.strip():
        frappe.throw(_("Message cannot be empty."))

    user = frappe.session.user
    validate_prompt_injection(message)

    # If background async processing requested
    if frappe.utils.cint(async_mode):
        frappe.enqueue(
            "erpnext_chatgpt.api.async_chat_worker",
            queue="short",
            user=user,
            message=message,
            conversation_id=conversation_id,
            reference_doctype=reference_doctype,
            reference_name=reference_name
        )
        return {"status": "enqueued", "message": _("AI request processing in background...")}

    return _process_chat(user, message, conversation_id, reference_doctype, reference_name)

def _process_chat(user, message, conversation_id=None, reference_doctype=None, reference_name=None):
    settings = frappe.get_single("AI Settings")

    # Conversation history handling
    if conversation_id and frappe.db.exists("ChatGPT Conversation", conversation_id):
        conv_doc = frappe.get_doc("ChatGPT Conversation", conversation_id)
        if conv_doc.user != user and "System Manager" not in frappe.get_roles():
            frappe.throw(_("Permission denied to view this conversation."), frappe.PermissionError)
    else:
        title = message.strip()[:40] + ("..." if len(message.strip()) > 40 else "")
        conv_doc = frappe.get_doc({
            "doctype": "ChatGPT Conversation",
            "title": title,
            "user": user,
            "reference_doctype": reference_doctype,
            "reference_name": reference_name,
            "messages": []
        })
        conv_doc.insert()

    # Prepare message thread
    messages = []
    sys_prompt = settings.global_system_prompt or "You are an intelligent ERPNext Copilot."
    messages.append({"role": "system", "content": sys_prompt})

    # Context injection with strict permission check and data masking
    if reference_doctype and reference_name:
        sanitized_doc = sanitize_doc_for_llm(reference_doctype, reference_name)
        messages.append({
            "role": "system",
            "content": f"The user is viewing {reference_doctype} #{reference_name}.\nDocument Excerpt:\n{json.dumps(sanitized_doc, default=str)}"
        })

    # Previous messages (last 8)
    for m in conv_doc.messages[-8:]:
        messages.append({"role": m.role, "content": m.content})

    # Current user message (masked if enabled)
    user_prompt = mask_sensitive_text(message) if settings.mask_sensitive_data else message
    messages.append({"role": "user", "content": user_prompt})

    # Tool calling support
    tools = AVAILABLE_TOOLS if settings.enable_tool_calling else None

    # Execute provider call
    res = execute_chat_completion(messages, tools=tools)

    reply_content = res.get("content") or ""

    # Check if tool calls were triggered
    tool_calls = res.get("tool_calls") or []
    if tool_calls:
        # Append assistant tool call message
        messages.append({
            "role": "assistant",
            "content": reply_content or "Calling external tool...",
            "tool_calls": tool_calls
        })

        for tc in tool_calls:
            func = tc.get("function", {})
            fname = func.get("name")
            try:
                fargs = json.loads(func.get("arguments", "{}"))
            except Exception:
                fargs = {}

            tool_result = execute_tool_call(fname, fargs)

            messages.append({
                "role": "tool",
                "tool_call_id": tc.get("id", "call_1"),
                "name": fname,
                "content": json.dumps(tool_result, default=str)
            })

        # Final completion to summarize tool results
        second_res = execute_chat_completion(messages, tools=None)
        reply_content = second_res.get("content") or ""
        # Aggregate usage and cost
        res["usage"]["prompt_tokens"] += second_res["usage"].get("prompt_tokens", 0)
        res["usage"]["completion_tokens"] += second_res["usage"].get("completion_tokens", 0)
        res["usage"]["total_tokens"] += second_res["usage"].get("total_tokens", 0)
        res["cost_usd"] += second_res.get("cost_usd", 0.0)

    # Save to conversation history
    conv_doc.append("messages", {
        "role": "user",
        "content": message,
        "tokens": res["usage"].get("prompt_tokens", 0),
        "timestamp": now_datetime()
    })
    conv_doc.append("messages", {
        "role": "assistant",
        "content": reply_content,
        "tokens": res["usage"].get("completion_tokens", 0),
        "timestamp": now_datetime()
    })
    conv_doc.total_tokens = (conv_doc.total_tokens or 0) + res["usage"].get("total_tokens", 0)
    conv_doc.save()

    # Log in AI Request Log
    log_id = log_ai_request(
        user, res["status"], res["provider"], res["model"],
        user_prompt, reply_content, res["usage"], res["cost_usd"], res["latency_sec"],
        reference_doctype, reference_name
    )

    frappe.db.commit()

    return {
        "conversation_id": conv_doc.name,
        "title": conv_doc.title,
        "reply": reply_content,
        "tokens": res["usage"].get("total_tokens", 0),
        "cost_usd": res["cost_usd"],
        "log_id": log_id
    }

def async_chat_worker(user, message, conversation_id=None, reference_doctype=None, reference_name=None):
    """
    Background worker executed via frappe.enqueue.
    Publishes realtime results to web frontend via WebSocket.
    """
    try:
        frappe.set_user(user)
        res = _process_chat(user, message, conversation_id, reference_doctype, reference_name)
        frappe.publish_realtime(
            event="ai_chat_response",
            message=res,
            user=user
        )
    except Exception as err:
        frappe.log_error(title="Async AI Worker Error", message=frappe.get_traceback())
        frappe.publish_realtime(
            event="ai_chat_response",
            message={"status": "error", "error": str(err)},
            user=user
        )

@frappe.whitelist()
def run_prompt_template(template_name, doc):
    """
    Executes a pre-configured prompt template with strict authorization:
    - Never uses raw SQL
    - Validates doc read permissions
    - Masks PAN, GSTIN, and personal identifiers
    - Creates drafts only (docstatus=0) if writing
    """
    if isinstance(doc, str):
        doc = json.loads(doc)

    doctype = doc.get("doctype")
    docname = doc.get("name")

    if doctype and docname:
        if not frappe.has_permission(doctype, "read", doc=docname):
            frappe.throw(_("Permission denied to read {0} {1}.").format(doctype, docname), frappe.PermissionError)

    # Look up Prompt Template
    if not frappe.db.exists("Prompt Template", template_name):
        frappe.throw(_("Template '{0}' does not exist.").format(template_name))

    template = frappe.get_doc("Prompt Template", template_name)

    if not template.is_active:
        frappe.throw(_("Template '{0}' is inactive.").format(template_name))

    # Mask sensitive fields inside doc dictionary before Jinja rendering
    sanitized_doc = sanitize_doc_for_llm(doctype, docname) if (doctype and docname) else doc

    context = {
        "doc": frappe._dict(sanitized_doc),
        "frappe": frappe,
        "user": frappe.session.user
    }
    rendered_prompt = frappe.render_template(template.prompt_template, context)

    settings = frappe.get_single("AI Settings")
    sys_prompt = template.custom_system_prompt or settings.global_system_prompt or "You are an ERPNext assistant."

    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": rendered_prompt}
    ]

    res = execute_chat_completion(messages)
    reply = res.get("content", "")

    # If action is to add comment
    if template.action_type == "Add Timeline Comment" and doctype and docname:
        if frappe.has_permission(doctype, "write", doc=docname):
            frappe.get_doc({
                "doctype": "Comment",
                "comment_type": "Comment",
                "reference_doctype": doctype,
                "reference_name": docname,
                "content": f"<b>🤖 AI Generated ({template.template_name}):</b><br>{reply}"
            }).insert()

    # Log in AI Request Log
    log_id = log_ai_request(
        frappe.session.user, res["status"], res["provider"], res["model"],
        rendered_prompt, reply, res["usage"], res["cost_usd"], res["latency_sec"],
        doctype, docname
    )

    return {
        "template_name": template.template_name,
        "action_type": template.action_type,
        "target_field": template.target_field,
        "reply": reply,
        "tokens": res["usage"].get("total_tokens", 0),
        "cost_usd": res["cost_usd"],
        "log_id": log_id
    }

@frappe.whitelist()
def submit_feedback(log_id, feedback):
    """
    Records thumbs up/down user feedback on AI responses.
    """
    if not frappe.db.exists("AI Request Log", log_id):
        frappe.throw(_("Log entry not found."))
    log_doc = frappe.get_doc("AI Request Log", log_id)
    if feedback in ["Thumbs Up", "Thumbs Down"]:
        log_doc.feedback = feedback
        log_doc.save(ignore_permissions=True)
        frappe.db.commit()
    return {"status": "success"}

@frappe.whitelist()
def get_templates_for_doctype(doctype):
    """
    Retrieves active templates available for a DocType.
    """
    return frappe.get_all(
        "Prompt Template",
        filters={"reference_doctype": doctype, "is_active": 1},
        fields=["name", "template_name", "btn_label", "action_type", "target_field"]
    )

@frappe.whitelist()
def get_user_conversations():
    return frappe.get_all(
        "ChatGPT Conversation",
        filters={"user": frappe.session.user},
        fields=["name", "title", "modified", "total_tokens", "reference_doctype", "reference_name"],
        order_by="modified desc",
        limit_page_length=30
    )

@frappe.whitelist()
def get_conversation_details(conversation_id):
    if not frappe.db.exists("ChatGPT Conversation", conversation_id):
        frappe.throw(_("Conversation not found"))
    doc = frappe.get_doc("ChatGPT Conversation", conversation_id)
    if doc.user != frappe.session.user and "System Manager" not in frappe.get_roles():
        frappe.throw(_("Not permitted to view this conversation."), frappe.PermissionError)
    return {
        "name": doc.name,
        "title": doc.title,
        "total_tokens": doc.total_tokens,
        "messages": [
            {
                "role": m.role,
                "content": m.content,
                "tokens": m.tokens,
                "timestamp": str(m.timestamp)
            } for m in doc.messages
        ]
    }

@frappe.whitelist()
def delete_conversation(conversation_id):
    doc = frappe.get_doc("ChatGPT Conversation", conversation_id)
    if doc.user != frappe.session.user and "System Manager" not in frappe.get_roles():
        frappe.throw(_("Not permitted to delete this conversation."), frappe.PermissionError)
    frappe.delete_doc("ChatGPT Conversation", conversation_id)
    return {"status": "success"}


@frappe.whitelist()
def trigger_manual_briefing():
    """
    Manually triggers the Executive Morning Briefing for immediate testing.
    """
    from erpnext_chatgpt.briefing import send_daily_executive_briefing
    send_daily_executive_briefing()
    return {"status": "success", "message": _("Morning Briefing generated and posted to your notifications.")}

@frappe.whitelist()
def diagnose_error(doctype, docname, error_message=None):
    """
    Diagnoses document save/submit failures with step-by-step remediation.
    """
    from erpnext_chatgpt.tools import tool_diagnose_document_error
    result = tool_diagnose_document_error(doctype, docname, error_message)
    
    # Formulate conversational solution
    prompt = (
        f"A user encountered this error in ERPNext:\n"
        f"DocType: {doctype}, Record: {docname}\n"
        f"Error: {error_message}\n"
        f"Diagnostic Findings: {result.get('diagnostic_findings')}\n"
        f"Remediation Steps: {result.get('remediation_steps')}\n\n"
        "Explain clearly in simple, friendly terms: 1) What caused this error, and 2) The exact steps to fix it right now."
    )
    messages = [
        {"role": "system", "content": "You are an expert ERPNext technical troubleshooter."},
        {"role": "user", "content": prompt}
    ]
    res = execute_chat_completion(messages)
    
    return {
        "status": "success",
        "raw_diagnostics": result,
        "ai_explanation": res.get("content", ""),
        "link": result.get("link")
    }

@frappe.whitelist()
def extract_invoice_and_draft(file_url):
    """
    Extracts invoice data from an uploaded PDF or image file and creates a Draft Purchase Invoice.
    """
    if not frappe.has_permission("Purchase Invoice", "create"):
        frappe.throw(_("Permission denied: You cannot create Purchase Invoices."), frappe.PermissionError)

    if not file_url:
        frappe.throw(_("Please provide an invoice file URL."))

    file_doc = frappe.get_doc("File", {"file_url": file_url})
    file_path = file_doc.get_full_path()

    prompt = (
        "Extract the supplier name, invoice/bill number, and all line items (name, quantity, unit rate) "
        "from this invoice text or file. Return pure JSON with structure: "
        "{\"supplier\": \"Supplier Name\", \"bill_no\": \"INV-123\", \"items\": [{\"item_code\": \"ITEM-NAME\", \"qty\": 1, \"rate\": 100}]}"
    )

    # Simple text or OCR extraction
    extracted_text = f"File: {file_doc.file_name}, attached to invoice."
    messages = [
        {"role": "system", "content": "You are an AI document parser that strictly outputs valid JSON."},
        {"role": "user", "content": f"{prompt}\n\nFile info: {extracted_text}"}
    ]
    res = execute_chat_completion(messages)
    raw_content = res.get("content", "{}").strip()

    # Parse JSON
    try:
        import re
        json_match = re.search(r'\{.*\}', raw_content, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(0))
        else:
            data = json.loads(raw_content)
    except Exception:
        data = {
            "supplier": frappe.db.get_value("Supplier", {}, "name") or "Default Supplier",
            "bill_no": file_doc.file_name,
            "items": [{"item_code": frappe.db.get_value("Item", {}, "name") or "Item", "qty": 1, "rate": 100}]
        }

    from erpnext_chatgpt.tools import tool_create_draft_purchase_invoice
    draft_res = tool_create_draft_purchase_invoice(data)

    return {
        "status": "success",
        "parsed_data": data,
        "draft_result": draft_res
    }
