"""
app.py — FastAPI web application for the support assistant.

Provides:
  - GET  /          → Chat UI (HTML page)
  - POST /api/chat  → Process a message
  - GET  /api/health → Health check
  - GET  /api/stats → Session statistics

Domain 2 requirements met:
  - Session handling (in-memory store)
  - Schema design (Pydantic models)
  - Configuration management (config.yaml, model pinning)
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from capstone.agent.orchestrator import SupportSession, process_message


# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Capstone Support Assistant",
    description="Production-grade support assistant integrating all 8 CCDV-F domains",
    version="1.0.0",
)

# In-memory session store
_sessions: dict[str, SupportSession] = {}


def _get_or_create_session(session_id: Optional[str] = None) -> tuple[str, SupportSession]:
    """Get an existing session or create a new one."""
    if session_id and session_id in _sessions:
        return session_id, _sessions[session_id]

    new_id = session_id or str(uuid.uuid4())[:8]
    session = SupportSession(session_id=new_id)
    _sessions[new_id] = session
    return new_id, session


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    customer_name: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    session_id: str
    blocked: bool
    tool_used: Optional[str] = None
    model_used: str
    turn_number: int
    cost_usd: float


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def chat_ui():
    """Serve the chat UI."""
    return CHAT_HTML


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Process a chat message."""
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    session_id, session = _get_or_create_session(request.session_id)

    if request.customer_name:
        session.set_customer_info(request.customer_name)

    result = process_message(session, request.message)

    return ChatResponse(
        response=result["response"],
        session_id=session_id,
        blocked=result["blocked"],
        tool_used=result.get("tool_used"),
        model_used=result["model_used"],
        turn_number=session.context_manager.current_turn,
        cost_usd=result["cost"].get("cost_usd", 0.0),
    )


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "active_sessions": len(_sessions),
        "version": "1.0.0",
    }


@app.get("/api/stats")
async def stats():
    """Get statistics across all sessions."""
    total_turns = sum(s.context_manager.current_turn for s in _sessions.values())
    total_cost = sum(s.cost_tracker.get_total_cost() for s in _sessions.values())
    hook_stats = {}
    for s in _sessions.values():
        h = s.formatting_hook.get_stats()
        for k, v in h.items():
            if isinstance(v, (int, float)):
                hook_stats[k] = hook_stats.get(k, 0) + v

    return {
        "sessions": len(_sessions),
        "total_turns": total_turns,
        "total_cost_usd": round(total_cost, 6),
        "formatting_hook": hook_stats,
    }


# ---------------------------------------------------------------------------
# Chat UI HTML
# ---------------------------------------------------------------------------

CHAT_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Support Assistant — Capstone</title>
    <meta name="description" content="AI-powered customer support assistant built with Claude">
    <style>
        :root {
            --bg-primary: #0f0f17;
            --bg-secondary: #1a1a2e;
            --bg-card: #16213e;
            --accent: #6c63ff;
            --accent-hover: #5a52e0;
            --text-primary: #e4e4f0;
            --text-secondary: #9d9daf;
            --border: #2a2a4a;
            --user-bubble: #6c63ff;
            --bot-bubble: #1e2a4a;
            --success: #4ade80;
            --warning: #fbbf24;
            --danger: #f87171;
        }

        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            height: 100vh;
            display: flex;
            flex-direction: column;
        }

        header {
            background: linear-gradient(135deg, var(--bg-secondary), var(--bg-card));
            border-bottom: 1px solid var(--border);
            padding: 16px 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        header h1 {
            font-size: 1.2rem;
            font-weight: 600;
            background: linear-gradient(90deg, var(--accent), #a78bfa);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .status-badge {
            font-size: 0.75rem;
            padding: 4px 12px;
            border-radius: 12px;
            background: rgba(74, 222, 128, 0.15);
            color: var(--success);
            border: 1px solid rgba(74, 222, 128, 0.3);
        }

        #chat-container {
            flex: 1;
            overflow-y: auto;
            padding: 24px;
            display: flex;
            flex-direction: column;
            gap: 16px;
        }

        .message {
            max-width: 75%;
            padding: 12px 16px;
            border-radius: 16px;
            line-height: 1.5;
            font-size: 0.9rem;
            animation: fadeIn 0.3s ease;
            white-space: pre-wrap;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(8px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .message.user {
            align-self: flex-end;
            background: var(--user-bubble);
            color: white;
            border-bottom-right-radius: 4px;
        }

        .message.bot {
            align-self: flex-start;
            background: var(--bot-bubble);
            border: 1px solid var(--border);
            border-bottom-left-radius: 4px;
        }

        .message .meta {
            font-size: 0.7rem;
            color: var(--text-secondary);
            margin-top: 6px;
            opacity: 0.7;
        }

        .message.bot .meta { color: var(--text-secondary); }
        .message.user .meta { color: rgba(255,255,255,0.6); }

        .message.blocked {
            border-left: 3px solid var(--danger);
        }

        #input-area {
            padding: 16px 24px;
            background: var(--bg-secondary);
            border-top: 1px solid var(--border);
            display: flex;
            gap: 12px;
        }

        #message-input {
            flex: 1;
            padding: 12px 16px;
            border-radius: 12px;
            border: 1px solid var(--border);
            background: var(--bg-primary);
            color: var(--text-primary);
            font-size: 0.9rem;
            outline: none;
            transition: border-color 0.2s;
        }

        #message-input:focus { border-color: var(--accent); }

        #send-btn {
            padding: 12px 24px;
            border-radius: 12px;
            border: none;
            background: var(--accent);
            color: white;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.2s, transform 0.1s;
        }

        #send-btn:hover { background: var(--accent-hover); }
        #send-btn:active { transform: scale(0.97); }
        #send-btn:disabled { opacity: 0.5; cursor: not-allowed; }

        .welcome {
            text-align: center;
            padding: 40px 20px;
            color: var(--text-secondary);
        }

        .welcome h2 {
            font-size: 1.5rem;
            margin-bottom: 8px;
            color: var(--text-primary);
        }

        .suggestions {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            justify-content: center;
            margin-top: 16px;
        }

        .suggestion {
            padding: 8px 14px;
            border-radius: 20px;
            border: 1px solid var(--border);
            background: var(--bg-card);
            color: var(--text-secondary);
            font-size: 0.8rem;
            cursor: pointer;
            transition: all 0.2s;
        }

        .suggestion:hover {
            border-color: var(--accent);
            color: var(--text-primary);
        }
    </style>
</head>
<body>
    <header>
        <h1>🛟 Support Assistant</h1>
        <span class="status-badge" id="status">● Online</span>
    </header>

    <div id="chat-container">
        <div class="welcome">
            <h2>How can I help you today?</h2>
            <p>I can look up orders, check your account, answer product questions, and more.</p>
            <div class="suggestions">
                <span class="suggestion" onclick="sendSuggestion(this)">What's the status of order ORD-1001?</span>
                <span class="suggestion" onclick="sendSuggestion(this)">What's the return policy?</span>
                <span class="suggestion" onclick="sendSuggestion(this)">Look up account sarah.chen@email.com</span>
                <span class="suggestion" onclick="sendSuggestion(this)">What shipping methods do you offer?</span>
            </div>
        </div>
    </div>

    <div id="input-area">
        <input type="text" id="message-input" placeholder="Type your message..." autofocus>
        <button id="send-btn" onclick="sendMessage()">Send</button>
    </div>

    <script>
        let sessionId = null;

        document.getElementById('message-input').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendMessage();
        });

        function sendSuggestion(el) {
            document.getElementById('message-input').value = el.textContent;
            sendMessage();
        }

        async function sendMessage() {
            const input = document.getElementById('message-input');
            const msg = input.value.trim();
            if (!msg) return;

            // Remove welcome message
            const welcome = document.querySelector('.welcome');
            if (welcome) welcome.remove();

            // Add user message
            addMessage(msg, 'user');
            input.value = '';
            document.getElementById('send-btn').disabled = true;

            try {
                const res = await fetch('/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: msg, session_id: sessionId }),
                });

                const data = await res.json();
                sessionId = data.session_id;

                const meta = [];
                if (data.tool_used) meta.push('Tool: ' + data.tool_used);
                meta.push('Model: ' + (data.model_used.includes('haiku') ? 'Haiku' : 'Sonnet'));
                meta.push('Turn: ' + data.turn_number);
                if (data.cost_usd > 0) meta.push('Cost: $' + data.cost_usd.toFixed(6));

                addMessage(data.response, 'bot', meta.join(' · '), data.blocked);
            } catch (err) {
                addMessage('Connection error. Please try again.', 'bot', 'Error', true);
            }

            document.getElementById('send-btn').disabled = false;
            input.focus();
        }

        function addMessage(text, role, meta = '', blocked = false) {
            const container = document.getElementById('chat-container');
            const div = document.createElement('div');
            div.className = 'message ' + role + (blocked ? ' blocked' : '');
            div.textContent = text;
            if (meta) {
                const metaDiv = document.createElement('div');
                metaDiv.className = 'meta';
                metaDiv.textContent = meta;
                div.appendChild(metaDiv);
            }
            container.appendChild(div);
            container.scrollTop = container.scrollHeight;
        }
    </script>
</body>
</html>
"""
