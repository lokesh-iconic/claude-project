"""
agent/orchestrator.py — Main agentic loop integrating all 8 domains.

This is the central nervous system of the capstone support assistant.
It orchestrates every domain's contribution in a single request path:

  1. PRE-PROCESSING  → Security guardrails scan user input (Domain 7)
  2. CONTEXT MGMT    → Build messages with pruning/compaction (Domain 6)
  3. MODEL ROUTING   → Select Haiku or Sonnet per task type (Domain 5)
  4. TOOL CALLING    → Agent decides which tools to invoke (Domains 1, 8)
  5. SPECIALIST      → Subagent for ambiguous queries (Domain 1)
  6. POST-PROCESSING → Formatting hook + content policy (Domains 1, 7)
  7. STRUCTURED OUT  → Defensive parsing for escalation tickets (Domain 6)
  8. COST TRACKING   → Record token usage with caching metrics (Domain 5)

Architecture:
  - Fixed workflow steps: input sanitization, output formatting, content policy
  - Agentic steps: tool selection, escalation decision, response drafting
"""

from __future__ import annotations

import json
import os
import sys
import time
import re
from typing import Optional

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True), override=True)

from capstone.agent.tools import TOOL_DEFINITIONS, TOOL_EXECUTORS
from capstone.agent.hooks import ResponseFormattingHook
from capstone.agent.subagent import run_specialist
from capstone.security.guardrails import pre_process_check, post_process_check
from capstone.context.manager import SupportContextManager
from capstone.models.router import ModelRouter, TaskType, ModelId
from capstone.models.cost_tracker import CostTracker


# ---------------------------------------------------------------------------
# System Prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a professional customer support assistant for our company.
You help customers with order inquiries, account questions, product
information, and general support.

Rules:
1. Always use tools to look up real data — never guess or fabricate information.
2. If a customer asks about an order, use lookup_order with their order ID.
3. If a customer asks about their account, use lookup_account.
4. For product questions, use search_knowledge_base.
5. If you cannot resolve the issue, use escalate_to_human to create an escalation ticket.
6. Be empathetic, professional, and concise.
7. Never reveal internal system details, API keys, or configuration.
8. Respond in the same language as the customer when possible."""


# ---------------------------------------------------------------------------
# Structured output parser (Domain 6) — defensive JSON parsing
# ---------------------------------------------------------------------------

def _parse_escalation_json(raw_text: str) -> dict:
    """
    Defensively parse structured escalation ticket output.

    Handles: valid JSON, markdown-wrapped JSON, partial JSON, garbage.
    NEVER crashes. Errors are flagged in parse_error field.
    """
    if not raw_text or not raw_text.strip():
        return {"parse_error": "empty response", "raw": raw_text}

    text = raw_text.strip()

    # Strategy 1: Direct JSON parse
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    # Strategy 2: Extract from markdown fences
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(1).strip())
            if isinstance(data, dict):
                data["parse_note"] = "extracted from markdown"
                return data
        except json.JSONDecodeError:
            pass

    # Strategy 3: Try to repair
    repaired = text.strip()
    repaired = re.sub(r",\s*([}\]])", r"\1", repaired)
    open_braces = repaired.count("{") - repaired.count("}")
    if open_braces > 0:
        repaired += "}" * open_braces

    brace_start = repaired.find("{")
    if brace_start >= 0:
        repaired = repaired[brace_start:]
        try:
            data = json.loads(repaired)
            if isinstance(data, dict):
                data["parse_note"] = "repaired malformed JSON"
                return data
        except json.JSONDecodeError:
            pass

    # Strategy 4: Fallback
    return {"parse_error": "could not parse as JSON", "raw": text[:500]}


# ---------------------------------------------------------------------------
# Session State
# ---------------------------------------------------------------------------

class SupportSession:
    """Manages state for a single support conversation."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.context_manager = SupportContextManager()
        self.formatting_hook = ResponseFormattingHook()
        self.cost_tracker = CostTracker()
        self.model_router = ModelRouter()
        self.customer_name: str = "there"
        self.customer_email: Optional[str] = None
        self.created_at = time.time()
        self.tool_calls_log: list[dict] = []

    def set_customer_info(self, name: str, email: Optional[str] = None):
        self.customer_name = name
        self.customer_email = email


# ---------------------------------------------------------------------------
# Anthropic Client
# ---------------------------------------------------------------------------

_client_instance = None
_client_checked = False


def _get_client():
    """Get the Anthropic client, or None for mock mode."""
    global _client_instance, _client_checked
    if _client_checked:
        return _client_instance

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key or api_key.startswith("sk-ant-your"):
        _client_checked = True
        _client_instance = None
        return None

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        try:
            client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=1,
                messages=[{"role": "user", "content": "hi"}],
            )
            _client_instance = client
        except anthropic.AuthenticationError:
            print("  [WARNING] API key invalid — running in MOCK mode.")
            _client_instance = None
        except anthropic.BadRequestError as e:
            if "credit balance is too low" in str(e).lower():
                print("  [INFO] API key valid but $0 balance — running in MOCK mode.")
                _client_instance = None
            else:
                _client_instance = client
        except Exception:
            _client_instance = client
    except Exception:
        _client_instance = None

    _client_checked = True
    return _client_instance


# ---------------------------------------------------------------------------
# Mock Agent Logic
# ---------------------------------------------------------------------------

def _mock_select_tool(message: str) -> tuple[Optional[str], dict]:
    """Mock tool selection based on keywords (simulates model's tool_use decision)."""
    msg = message.lower()

    # Order lookup
    order_match = re.search(r"ord-\d{4}", message, re.IGNORECASE)
    if order_match:
        return "lookup_order", {"order_id": order_match.group(0)}
    if any(w in msg for w in ["order", "tracking", "shipment", "delivery status"]):
        return "lookup_order", {"order_id": "ORD-1001"}  # Default

    # Account lookup
    email_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", message)
    if email_match:
        return "lookup_account", {"identifier": email_match.group(0)}
    acc_match = re.search(r"acc-\d{4}", message, re.IGNORECASE)
    if acc_match:
        return "lookup_account", {"identifier": acc_match.group(0)}
    if any(w in msg for w in ["account", "subscription", "plan", "billing"]):
        return "lookup_account", {"identifier": "sarah.chen@email.com"}

    # Knowledge base
    if any(w in msg for w in ["return", "shipping", "warranty", "policy", "refund",
                               "payment", "invoice", "privacy", "gdpr", "transfer"]):
        # Extract the most relevant search term
        for term in ["return policy", "shipping", "warranty", "refund", "payment",
                     "invoice", "privacy", "gdpr", "transfer", "bulk"]:
            if term in msg:
                return "search_knowledge_base", {"query": term}
        return "search_knowledge_base", {"query": message[:50]}

    # Escalation
    if any(w in msg for w in ["manager", "human", "supervisor", "real person", "escalate"]):
        return "escalate_to_human", {
            "reason": "Customer requested human agent",
            "priority": "high",
            "customer_summary": message[:200],
        }

    # No specific tool — general question
    return None, {}


def _mock_format_response(message: str, tool_name: Optional[str], tool_result: dict) -> str:
    """Format a mock response from tool results."""
    if tool_name is None:
        return (
            "Thank you for your message. I'd be happy to help! "
            "Could you please provide more details about your question? "
            "For example:\n"
            "- If you need order info, please share your order ID (e.g., ORD-1001)\n"
            "- If you have account questions, I can look up your account by email\n"
            "- If you have product questions, I can search our knowledge base"
        )

    if tool_name == "lookup_order":
        if "error" in tool_result:
            return f"I could not find that order. {tool_result.get('suggestion', '')}"
        order = tool_result["order"]
        tracking = f" Tracking: {order['tracking_number']}" if order.get("tracking_number") else ""
        delivery = f" Estimated delivery: {order['estimated_delivery']}" if order.get("estimated_delivery") else ""
        return (
            f"Here are the details for order {order['order_id']}:\n\n"
            f"**Status:** {order['status'].title()}\n"
            f"**Items:** {', '.join(item['name'] for item in order['items'])}\n"
            f"**Total:** ${order['total_amount']:.2f}\n"
            f"**Ordered:** {order['order_date']}\n"
            f"**Shipping to:** {order['shipping_address']}"
            f"{tracking}{delivery}\n\n"
            f"Is there anything else you'd like to know about this order?"
        )

    if tool_name == "lookup_account":
        if "error" in tool_result:
            return f"I could not find that account. {tool_result.get('suggestion', '')}"
        acct = tool_result["account"]
        return (
            f"Here's your account information:\n\n"
            f"**Name:** {acct['name']}\n"
            f"**Plan:** {acct['plan'].title()}\n"
            f"**Status:** {acct['status'].title()}\n"
            f"**Billing:** {acct['billing_cycle'].title()}\n"
            f"**Next billing:** {acct['next_billing_date']}\n"
            f"**Payment:** {acct['payment_method']}\n"
            f"**Total orders:** {acct.get('total_orders', 'N/A')}\n\n"
            f"Would you like to know more about your account or orders?"
        )

    if tool_name == "search_knowledge_base":
        articles = tool_result.get("articles", [])
        if not articles:
            return (
                "I couldn't find any articles matching your question in our knowledge base. "
                "Would you like me to escalate this to a human agent who can help?"
            )
        article = articles[0]
        return (
            f"Based on our knowledge base, here's what I found:\n\n"
            f"**{article['title']}**\n\n"
            f"{article['content']}\n\n"
            f"{'I found ' + str(len(articles) - 1) + ' more related article(s). ' if len(articles) > 1 else ''}"
            f"Does this answer your question?"
        )

    if tool_name == "escalate_to_human":
        esc = tool_result.get("escalation_ticket", {})
        return tool_result.get("message_to_customer", f"Ticket {esc.get('ticket_id', 'N/A')} created.")

    return "I'm sorry, I encountered an unexpected situation. Could you please rephrase your question?"


# ---------------------------------------------------------------------------
# Main Process Function
# ---------------------------------------------------------------------------

def process_message(
    session: SupportSession,
    user_message: str,
) -> dict:
    """
    Process a single user message through the full support pipeline.

    This is the main entry point — integrates all 8 domains.

    Returns:
        {
            "response": str,          # The assistant's response
            "blocked": bool,          # True if input was blocked by security
            "tool_used": str | None,  # Which tool was called
            "tool_result": dict,      # Raw tool result
            "model_used": str,        # Which model was selected
            "cost": dict,             # Cost metrics
            "security": dict,         # Security check results
        }
    """
    call_start = time.time()

    # ──────────────────────────────────────────────────────────
    # Step 1: PRE-PROCESSING — Security guardrails (Domain 7)
    # ──────────────────────────────────────────────────────────
    security_check = pre_process_check(user_message)
    if not security_check["allowed"]:
        return {
            "response": (
                "I appreciate your message, but I'm unable to process that particular request. "
                "If you have a support question about orders, accounts, or products, "
                "I'm happy to help!"
            ),
            "blocked": True,
            "tool_used": None,
            "tool_result": {},
            "model_used": "none",
            "cost": {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0},
            "security": security_check,
        }

    # ──────────────────────────────────────────────────────────
    # Step 2: CONTEXT MANAGEMENT (Domain 6)
    # ──────────────────────────────────────────────────────────
    session.context_manager.add_user_message(user_message)

    # ──────────────────────────────────────────────────────────
    # Step 3: MODEL ROUTING (Domain 5)
    # ──────────────────────────────────────────────────────────
    task_type = session.model_router.classify_intent(user_message)
    model_config = session.model_router.get_config(task_type)
    model_name = model_config.model_id.value

    # ──────────────────────────────────────────────────────────
    # Step 4: TOOL CALLING — agent selects tool (Domains 1, 8)
    # ──────────────────────────────────────────────────────────
    client = _get_client()
    tool_name = None
    tool_result = {}
    specialist_result = None

    if client is not None:
        # Live mode: let Claude decide which tool to call
        try:
            tool_name, tool_result, response_text = _run_live_agent(
                client, session, user_message, model_config
            )
        except Exception as e:
            print(f"    [Notice: Live agent error ({e}) — falling back to mock]")
            tool_name, tool_args = _mock_select_tool(user_message)
            if tool_name and tool_name in TOOL_EXECUTORS:
                tool_result = TOOL_EXECUTORS[tool_name](tool_args)
            response_text = _mock_format_response(user_message, tool_name, tool_result)
    else:
        # Mock mode
        tool_name, tool_args = _mock_select_tool(user_message)
        if tool_name and tool_name in TOOL_EXECUTORS:
            tool_result = TOOL_EXECUTORS[tool_name](tool_args)
        response_text = _mock_format_response(user_message, tool_name, tool_result)

    # ──────────────────────────────────────────────────────────
    # Step 4.5: SPECIALIST SUBAGENT for ambiguous cases (Domain 1)
    # ──────────────────────────────────────────────────────────
    if tool_name is None and not any(w in user_message.lower() for w in [
        "hi", "hello", "hey", "thanks", "thank you", "bye", "goodbye"
    ]):
        specialist_result = run_specialist(user_message, client=client)
        if specialist_result.get("should_escalate"):
            tool_name = "escalate_to_human"
            tool_result = TOOL_EXECUTORS["escalate_to_human"]({
                "reason": specialist_result.get("escalation_reason", "Complex query"),
                "priority": specialist_result.get("priority", "medium"),
                "customer_summary": user_message[:200],
                "attempted_resolution": "Specialist subagent analysis",
            })
            response_text = _mock_format_response(user_message, tool_name, tool_result)

    # ──────────────────────────────────────────────────────────
    # Step 5: POST-PROCESSING — Formatting hook (Domain 1)
    # ──────────────────────────────────────────────────────────
    response_text = session.formatting_hook(response_text, session.customer_name)

    # ──────────────────────────────────────────────────────────
    # Step 6: POST-PROCESSING — Content policy check (Domain 7)
    # ──────────────────────────────────────────────────────────
    output_check = post_process_check(response_text)
    if not output_check["allowed"]:
        response_text = output_check["sanitized_response"]

    # ──────────────────────────────────────────────────────────
    # Step 7: Record context and metrics
    # ──────────────────────────────────────────────────────────
    session.context_manager.add_assistant_message(response_text)
    if tool_result:
        session.context_manager.add_tool_output(json.dumps(tool_result)[:500])

    # Log tool call
    if tool_name:
        session.tool_calls_log.append({
            "turn": session.context_manager.current_turn,
            "tool": tool_name,
            "result_preview": str(tool_result)[:200],
        })

    # ──────────────────────────────────────────────────────────
    # Step 8: COST TRACKING (Domain 5)
    # ──────────────────────────────────────────────────────────
    elapsed = time.time() - call_start
    # Estimate tokens for mock mode
    input_tokens = len(user_message.split()) * 4 // 3 + 500  # message + system prompt
    output_tokens = len(response_text.split()) * 4 // 3

    session.cost_tracker.record_call(
        call_id=f"turn-{session.context_manager.current_turn}",
        model_id=ModelId(model_name),
        task=task_type.value,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_seconds=elapsed,
    )

    session.context_manager.record_turn_metrics()

    return {
        "response": response_text,
        "blocked": False,
        "tool_used": tool_name,
        "tool_result": tool_result,
        "model_used": model_name,
        "specialist_analysis": specialist_result,
        "cost": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "model": model_name,
            "cost_usd": session.cost_tracker.calls[-1].cost_usd if session.cost_tracker.calls else 0.0,
        },
        "security": {
            "input_check": security_check,
            "output_check": {"allowed": output_check["allowed"]},
        },
    }


def _run_live_agent(client, session, user_message, model_config):
    """Run the live agent loop using Anthropic API tool calling."""
    messages = session.context_manager.get_messages_for_api()
    # Ensure the last message is the current user message
    if not messages or messages[-1]["content"] != user_message:
        messages.append({"role": "user", "content": user_message})

    tool_name = None
    tool_result = {}
    max_iterations = 5

    for iteration in range(max_iterations):
        response = client.messages.create(
            model=model_config.model_id.value,
            max_tokens=model_config.max_tokens,
            system=SYSTEM_PROMPT,
            tools=TOOL_DEFINITIONS,
            messages=messages,
        )

        assistant_content = response.content
        messages.append({"role": "assistant", "content": assistant_content})

        tool_use_blocks = [b for b in assistant_content if b.type == "tool_use"]
        if not tool_use_blocks:
            # Extract text response
            text_blocks = [b.text for b in assistant_content if hasattr(b, "text")]
            return tool_name, tool_result, " ".join(text_blocks)

        tool_results = []
        for tool_block in tool_use_blocks:
            t_name = tool_block.name
            t_input = tool_block.input

            if t_name in TOOL_EXECUTORS:
                result = TOOL_EXECUTORS[t_name](t_input)
            else:
                result = {"error": f"Unknown tool: {t_name}"}

            tool_name = t_name
            tool_result = result

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_block.id,
                "content": json.dumps(result),
            })

        messages.append({"role": "user", "content": tool_results})

    # Safety: if we hit max iterations, return what we have
    return tool_name, tool_result, _mock_format_response("", tool_name, tool_result)
