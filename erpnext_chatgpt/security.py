# Copyright (c) 2026, Antigravity AI and contributors
# For license information, please see license.txt

import re
import frappe
from frappe import _

# Regex patterns for sensitive data masking
REGEX_PAN = re.compile(r'\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b')
REGEX_GSTIN = re.compile(r'\b[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}\b')
REGEX_CREDIT_CARD = re.compile(r'\b(?:\d{4}[ -]?){3}\d{4}\b')
REGEX_BANK_ACCOUNT = re.compile(r'\b(?:account|acc|a/c)\s*[:#]?\s*(\d{9,18})\b', re.IGNORECASE)
REGEX_AADHAAR = re.compile(r'\b[2-9]{1}[0-9]{3}\s[0-9]{4}\s[0-9]{4}\b')

def mask_sensitive_text(text: str) -> str:
    """
    Masks sensitive financial and personal identification data before transmitting to LLMs.
    """
    if not text or not isinstance(text, str):
        return text

    # Mask PAN
    text = REGEX_PAN.sub("[MASKED_PAN]", text)
    # Mask GSTIN
    text = REGEX_GSTIN.sub("[MASKED_GSTIN]", text)
    # Mask Credit Cards
    text = REGEX_CREDIT_CARD.sub("[MASKED_CARD]", text)
    # Mask Bank Accounts
    text = REGEX_BANK_ACCOUNT.sub(r"account: [MASKED_ACC]", text)
    # Mask Aadhaar
    text = REGEX_AADHAAR.sub("[MASKED_AADHAAR]", text)

    return text

def sanitize_doc_for_llm(doctype: str, docname: str, allowed_fields: list = None) -> dict:
    """
    Securely fetches and sanitizes a document:
    1. Strictly verifies user read permission using Frappe's security engine.
    2. Strips private keys, passwords, hashes, and internal metadata.
    3. Masks sensitive financial identifiers.
    """
    if not frappe.has_permission(doctype, "read", doc=docname):
        frappe.throw(_("Security Error: You do not have permission to access {0} {1}.").format(doctype, docname), frappe.PermissionError)

    doc = frappe.get_doc(doctype, docname)
    raw_data = doc.as_dict()

    forbidden_fields = {
        "password", "api_key", "api_secret", "secret", "auth_token",
        "pin", "otp", "salt", "reset_password_key", "_docstatus"
    }

    sanitized = {}
    for key, val in raw_data.items():
        if key.startswith("_") or key in forbidden_fields:
            continue
        if allowed_fields and key not in allowed_fields:
            continue

        if isinstance(val, str):
            sanitized[key] = mask_sensitive_text(val)
        else:
            sanitized[key] = val

    return sanitized

def validate_prompt_injection(prompt: str) -> bool:
    """
    Checks for direct system-override or escape patterns.
    """
    suspicious_patterns = [
        r"ignore\s+(all\s+)?(previous|prior)\s+instructions",
        r"system\s*:\s*you\s+are\s+now",
        r"disregard\s+the\s+system\s+prompt"
    ]
    for pattern in suspicious_patterns:
        if re.search(pattern, prompt, re.IGNORECASE):
            frappe.log_error(title="Prompt Injection Alert", message=f"User: {frappe.session.user} Prompt: {prompt}")
            frappe.throw(_("Potential prompt manipulation detected. Request blocked for security."), frappe.ValidationError)
    return True

