# Copyright (c) 2026, Antigravity AI and contributors
# For license information, please see license.txt

import time
import requests
import frappe
from frappe import _
from frappe.utils import flt, now_datetime, get_first_day, nowdate

# Model pricing in USD per 1M tokens: (input_price, output_price)
PRICING_TABLE = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4-turbo": (10.00, 30.00),
    "gpt-3.5-turbo": (0.50, 1.50),
    "o1-mini": (3.00, 12.00),
    "claude-3-5-sonnet-20241022": (3.00, 15.00),
    "claude-3-haiku-20240307": (0.25, 1.25),
    "ollama": (0.00, 0.00),
    "local": (0.00, 0.00)
}

def calculate_token_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    rate = PRICING_TABLE.get(model, (1.00, 3.00))
    input_cost = (prompt_tokens / 1_000_000.0) * rate[0]
    output_cost = (completion_tokens / 1_000_000.0) * rate[1]
    return round(input_cost + output_cost, 6)

def check_budget_and_limits(settings, user: str):
    """
    Validates per-user daily limits and overall monthly budget cap.
    """
    if settings.site_disabled:
        frappe.throw(_("AI Services are temporarily disabled on this site by the administrator."), frappe.PermissionError)

    # 1. Per-User Daily Limit
    if settings.daily_limit_per_user and settings.daily_limit_per_user > 0:
        today_start = f"{nowdate()} 00:00:00"
        user_requests_today = frappe.db.count(
            "AI Request Log",
            filters={
                "user": user,
                "creation": [">=", today_start],
                "status": "Success"
            }
        )
        if user_requests_today >= settings.daily_limit_per_user:
            frappe.throw(
                _("Daily AI request limit ({0}) exceeded for user {1}. Please try again tomorrow.").format(settings.daily_limit_per_user, user),
                frappe.ValidationError
            )

    # 2. Monthly Budget Cap
    if settings.monthly_budget_cap_usd and settings.monthly_budget_cap_usd > 0:
        first_day_of_month = f"{get_first_day(nowdate())} 00:00:00"
        monthly_spend = frappe.db.sql("""
            SELECT SUM(estimated_cost_usd)
            FROM `tabAI Request Log`
            WHERE creation >= %s AND status = 'Success'
        """, (first_day_of_month,))[0][0] or 0.0

        if flt(monthly_spend) >= flt(settings.monthly_budget_cap_usd):
            frappe.throw(
                _("Monthly AI budget cap (${0}) reached. Contact your System Administrator to adjust limits.").format(settings.monthly_budget_cap_usd),
                frappe.ValidationError
            )

def execute_chat_completion(messages: list, tools: list = None, tool_choice: str = "auto", model_override: str = None) -> dict:
    """
    Pluggable LLM dispatcher supporting OpenAI, Azure, Anthropic, and local Ollama.
    Features automated retry with exponential backoff on 429 and 5xx errors.
    """
    settings = frappe.get_single("AI Settings")
    if not settings.enabled:
        frappe.throw(_("AI Copilot is disabled in AI Settings."))

    check_budget_and_limits(settings, frappe.session.user)

    provider = settings.provider or "OpenAI"
    model = model_override or settings.model or "gpt-4o-mini"
    temperature = flt(settings.temperature or 0.7)
    max_tokens = int(settings.max_tokens or 1000)
    api_key = settings.get_password("api_key")

    start_time = time.time()
    retry_delays = [1, 2, 4]  # Exponential backoff schedule

    last_error = None
    for attempt, delay in enumerate([0] + retry_delays):
        if delay > 0:
            time.sleep(delay)

        try:
            if provider == "Anthropic":
                resp_content, usage, tool_calls = call_anthropic(settings, api_key, model, messages, temperature, max_tokens)
            else:
                # OpenAI / Azure / Ollama compatible
                resp_content, usage, tool_calls = call_openai_compatible(settings, api_key, model, messages, temperature, max_tokens, tools, tool_choice)

            latency = round(time.time() - start_time, 2)
            cost = calculate_token_cost(model, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))

            return {
                "content": resp_content,
                "tool_calls": tool_calls,
                "usage": usage,
                "cost_usd": cost,
                "latency_sec": latency,
                "model": model,
                "provider": provider,
                "status": "Success"
            }

        except requests.exceptions.HTTPError as http_err:
            status_code = http_err.response.status_code if http_err.response else 500
            last_error = http_err
            # Retry on Rate Limit (429) or Server Errors (500, 502, 503, 504)
            if status_code in (429, 500, 502, 503, 504) and attempt < len(retry_delays):
                continue
            break
        except Exception as err:
            last_error = err
            break

    # If all attempts fail, log and throw friendly message
    latency = round(time.time() - start_time, 2)
    frappe.log_error(title="AI Provider Request Failed", message=f"Provider: {provider}, Model: {model}, Error: {str(last_error)}")
    frappe.throw(_("AI Service Error: {0}").format(str(last_error)), frappe.OperationalError)

def call_openai_compatible(settings, api_key, model, messages, temperature, max_tokens, tools=None, tool_choice="auto"):
    base_url = (settings.base_url or "https://api.openai.com/v1").rstrip("/")
    headers = {
        "Content-Type": "application/json"
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    if settings.organization_id:
        headers["OpenAI-Organization"] = settings.organization_id

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = tool_choice

    url = f"{base_url}/chat/completions"
    resp = requests.post(url, headers=headers, json=payload, timeout=60)

    if resp.status_code != 200:
        err_msg = resp.text
        try:
            err_json = resp.json()
            err_msg = err_json.get("error", {}).get("message", resp.text)
        except Exception:
            pass
        raise requests.exceptions.HTTPError(err_msg, response=resp)

    data = resp.json()
    choice = data["choices"][0]
    message = choice.get("message", {})
    content = message.get("content", "")
    tool_calls = message.get("tool_calls", [])

    raw_usage = data.get("usage", {})
    usage = {
        "prompt_tokens": raw_usage.get("prompt_tokens", 0),
        "completion_tokens": raw_usage.get("completion_tokens", 0),
        "total_tokens": raw_usage.get("total_tokens", 0)
    }

    return content, usage, tool_calls

def call_anthropic(settings, api_key, model, messages, temperature, max_tokens):
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json"
    }

    # Extract system prompt if present
    system_text = ""
    anthropic_msgs = []
    for m in messages:
        if m["role"] == "system":
            system_text += m["content"] + "\n"
        else:
            anthropic_msgs.append({"role": m["role"], "content": m["content"]})

    payload = {
        "model": model,
        "messages": anthropic_msgs,
        "max_tokens": max_tokens,
        "temperature": temperature
    }
    if system_text:
        payload["system"] = system_text.strip()

    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    if resp.status_code != 200:
        raise requests.exceptions.HTTPError(resp.text, response=resp)

    data = resp.json()
    content = ""
    for block in data.get("content", []):
        if block.get("type") == "text":
            content += block.get("text", "")

    raw_usage = data.get("usage", {})
    usage = {
        "prompt_tokens": raw_usage.get("input_tokens", 0),
        "completion_tokens": raw_usage.get("output_tokens", 0),
        "total_tokens": raw_usage.get("input_tokens", 0) + raw_usage.get("output_tokens", 0)
    }

    return content, usage, []

