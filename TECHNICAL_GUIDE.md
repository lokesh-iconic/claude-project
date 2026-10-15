# Technical Guide — How This Repository Works and Why

This guide explains, module by module, what the code does, why it is built that way, and how
the core concepts (agentic loops, tool use, hooks, subagents, prompt caching, context
engineering, guardrails, MCP) work underneath. It describes the code as it is, including the
parts that are simulated in mock mode and the parts that are flawed on purpose.

File references are relative to the repository root.

---

## Table of Contents

1. [Big picture and shared design](#1-big-picture-and-shared-design)
2. [Foundations: how an LLM API call works](#2-foundations-how-an-llm-api-call-works)
3. [The agentic loop in depth](#3-the-agentic-loop-in-depth)
4. [Module 1 — Workflow vs. agent](#4-module-1--workflow-vs-agent)
5. [Module 2 — DocuQuery (application and integration)](#5-module-2--docuquery-application-and-integration)
6. [Module 3 — Claude Code configuration](#6-module-3--claude-code-configuration)
7. [Module 4 — Evals, tracing and debugging](#7-module-4--evals-tracing-and-debugging)
8. [Module 5 — Model selection and optimization](#8-module-5--model-selection-and-optimization)
9. [Module 6 — Prompt and context engineering](#9-module-6--prompt-and-context-engineering)
10. [Module 7 — Security and safety](#10-module-7--security-and-safety)
11. [Module 8 — Tools, Skills and MCP](#11-module-8--tools-skills-and-mcp)
12. [Capstone — the integrated support assistant](#12-capstone--the-integrated-support-assistant)
13. [Concept glossary](#13-concept-glossary)
14. [What is simulated, what is real, what is deliberate](#14-what-is-simulated-what-is-real-what-is-deliberate)
15. [Appendix A — Where each concept is used](#appendix-a--where-each-concept-is-used)

---

## 1. Big picture and shared design

The repository is a learning portfolio. Each numbered folder is one skill an AI-application
developer needs, and `capstone/` combines them into one customer-support assistant.

```
Module 1  Workflow vs agent        -> when code decides the steps vs when the model does
Module 2  DocuQuery API            -> streaming, caching, sessions, config, REST
Module 3  Claude Code config       -> CLAUDE.md, settings, commands, headless mode
Module 4  Eval/debug               -> telling a code bug from a model-output problem
Module 5  Model selection          -> cost / latency / quality trade-offs
Module 6  Prompt + context         -> keep long conversations reliable
Module 7  Security                 -> prompt injection, secrets, access control
Module 8  Tools / Skills / MCP     -> three ways to expose one capability
Capstone  All of the above         -> one assistant
```

### 1.1 Patterns repeated in every module

**Mock mode is the default.** Almost every module can run with no API key. When
`ANTHROPIC_API_KEY` is empty (or the placeholder from `.env.example`), a module uses
deterministic keyword-based stand-ins for the model. When a valid key is present, the
module creates a real `anthropic.Anthropic` client and uses it where a live path exists.

Why this design:
- Tests and CI are reproducible and cost nothing.
- The surrounding engineering (hooks, parsing, session handling, tracing) can be developed and
  verified without depending on a non-deterministic model.
- A reader can run the whole repository on a laptop with no account.

The price: results from mock mode demonstrate the *machinery*, not real model behaviour. Section
14 lists exactly what is simulated.

**Client bootstrap with graceful fallback.** Each module has a `_get_client()` function that:
1. returns `None` if there is no usable key;
2. otherwise builds the client and probes it (`models.list`, then a 1-token `messages.create`);
3. maps `AuthenticationError`, "credit balance too low", and `NotFoundError` (unknown model) to
   a warning plus `None`, so the program continues in mock mode instead of crashing mid-run;
4. caches the result in module globals (`_client_instance`, `_client_checked`) so the probe
   runs once per process.

**Pydantic for every structured value.** Tickets, classifications, answers and responses are
Pydantic models (`BaseModel`) or `str`-based `Enum`s. This gives validation at the boundary,
JSON-serializable constants, and automatic OpenAPI docs in FastAPI.

**Configuration over constants.** Model names, prompt versions, session timeouts and cache
settings live in `config.yaml` (module 2, capstone) or in registries (`ModelId` enums), not
scattered through code.

### 1.2 Repository layout

```
main.py                       runs modules 1-8 as subprocesses, prints a summary, writes output/run_report.md
pyproject.toml                dependencies (anthropic, fastapi, mcp, pydantic, pyyaml, rich, ...)
.env.example                  template for .env
1_agents_and_workflows/       workflow/, agent/, pydantic_ai_component/, tickets.py, shared.py
2_applications_and_integration/  app/ (FastAPI), config.yaml, sample_documents/, tests/
3_claude_code/                CLAUDE.md, .claude/, scripts/, validate_setup.py (templates)
4_eval_testing_and_debugging/ broken_app/, fixed_app/, mock_model.py, tracer.py, diagnosis/
5_model_selection_and_optimization/  models.py, tracker.py, task_a/b/c
6_prompt_and_context_engineering/    system_prompt.py, context_manager.py, structured_output.py, ...
7_security_and_safety/        vulnerable_app/, hardened_app/, payloads.py, layer_checks.py
8_tools_and_MCPs/             custom_tool/, skill/, mcp_server/, error_model.py
capstone/                     agent/, security/, models/, context/, data/, eval/, app.py
```

---

## 2. Foundations: how an LLM API call works

You need these ideas to understand everything else.

### 2.1 The Messages API is stateless

A call to `client.messages.create(...)` sends:

| Field | Meaning |
|-------|---------|
| `model` | which Claude model (for example `claude-sonnet-4-6`) |
| `max_tokens` | upper bound on tokens the model may generate |
| `system` | instructions that frame the whole conversation (a string, or a list of text blocks) |
| `messages` | the conversation so far: a list of `{role, content}` where role alternates `user` / `assistant` |
| `tools` | optional list of tool definitions the model may call |
| `temperature` etc. | sampling settings (this repo passes `temperature` through `extra_body` because the installed SDK has no typed argument for it) |

The model keeps **no memory** between calls. "A conversation" exists only because your code
resends the full `messages` list every time. That is why context management (module 6) matters:
whatever you resend costs tokens and eats the context window.

### 2.2 Tokens, cost and context window

A token is roughly three-quarters of a word. You pay per million input tokens and per million
output tokens (output is more expensive). The **context window** is the maximum
input + output a model can handle in one call. Code here estimates tokens as
`len(text.split()) * 4 // 3` or `len(text) // 4` when it cannot measure; the API reports exact
counts in `response.usage`.

### 2.3 Content blocks

A response's `content` is a list of blocks, not a string. The block types that matter here:

- `text` — ordinary output text.
- `tool_use` — the model asking your code to run a tool: `{id, name, input}`.
- `thinking` — extended-thinking reasoning (module 5).

You send results back as `tool_result` blocks inside a **user** message, each carrying the
`tool_use_id` it answers.

### 2.4 Tool use

You describe a tool with a name, a natural-language `description`, and a JSON Schema
(`input_schema`). The model never executes anything. It emits a `tool_use` block saying "call
`lookup_order` with `{"order_id": "ORD-1001"}`", your code runs it, and you return the result.
Good descriptions matter: they are the model's only guide to *when* to call each tool. This
is why module 8's descriptions say when to use each tool, not just what it does.

### 2.5 Prompt caching

Large, stable prefixes (such as a document) can be marked `cache_control: {"type":
"ephemeral"}`. The first call pays a one-time **cache write** (priced above normal input). Later
calls that begin with the identical prefix pay a **cache read** (roughly 10% of normal input
price). Caching is prefix-based: everything before the marker must be byte-identical, so the
stable content goes first and the variable content (conversation) goes last. The default
cache lifetime is short (minutes) and refreshes on each hit.

### 2.6 Streaming

`client.messages.stream(...)` yields text as it is generated instead of returning one finished
message. This lowers perceived latency. Module 2 turns the stream into Server-Sent Events.

### 2.7 Extended thinking

With `thinking={"type": "enabled", "budget_tokens": N}` the model produces reasoning blocks
before its answer. Thinking tokens are billed as output tokens, and `max_tokens` must be larger
than the budget. Use it for multi-step reasoning, not for simple classification.

### 2.8 Deterministic vs. probabilistic control

A prompt instruction ("always add a greeting") is a *request* to a probabilistic system. Code
(a hook, a regex, a permission check) is a *guarantee*. A recurring theme: use the prompt for
judgement and creativity, use code for rules that must hold every time.

---

## 3. The agentic loop in depth

This is the central concept of the repository. Modules 1, 4 and the capstone all contain one.

### 3.1 Workflow vs. agent

| | Workflow | Agent |
|---|----------|-------|
| Who chooses the next step? | Your code (fixed sequence) | The model, each turn |
| Control flow lives in | Python statements | The model's `tool_use` decisions |
| Data between steps | Python variables | The `messages` list |
| Cost / latency | Predictable (N calls) | Variable (depends on decisions) |
| Can it loop back or skip? | No | Yes |
| Best for | Well-structured, predictable inputs | Messy or open-ended inputs |

Rule of thumb used in this repo: start with a workflow; move to an agent only when measured
failures on variable inputs justify the added complexity.

### 3.2 The loop, step by step

```
messages = [ user: "process this ticket" ]

repeat up to MAX_ITERATIONS:
    response = model(system, tools, messages)           # 1. ask the model
    messages.append( assistant: response.content )      # 2. record what it said/asked
    tool_calls = [b for b in response.content if b.type == "tool_use"]
    if no tool_calls:                                   # 3. nothing to execute -> finished
        break
    results = []
    for call in tool_calls:                             # 4. execute each requested tool
        result = run_tool(call.name, call.input)
        result = post_tool_use_hook(call.name, call.input, result)   # 5. deterministic post-processing
        results.append( tool_result(call.id, result) )
    messages.append( user: results )                    # 6. feed results back as a user message
```

The real implementation is `run_agent_loop_live` in
[1_agents_and_workflows/agent/runner.py](1_agents_and_workflows/agent/runner.py).

What a conversation looks like after two iterations:

```
user       "Process this support ticket ... Ticket ID: TKT-001 ... Body: I was charged twice..."
assistant  [ tool_use(id=t1, name=classify_ticket, input={ticket_id, subject, body}) ]
user       [ tool_result(tool_use_id=t1, content='{"category":"billing","priority":"high",...}') ]
assistant  [ tool_use(id=t2, name=route_ticket, input={category:"billing", priority:"high", ...}) ]
user       [ tool_result(tool_use_id=t2, content='{"team":"billing","escalate":true,...}') ]
assistant  [ tool_use(id=t3, name=draft_response, ...) ]
user       [ tool_result(tool_use_id=t3, content='<hook-formatted draft>') ]
assistant  [ text "Classified as billing/high, routed to billing, draft ready." ]   <- no tool_use: loop ends
```

### 3.3 Details that matter

**Termination.** The loop in this repo ends when the model's response contains no `tool_use`
blocks. (The API also reports a `stop_reason`, where `tool_use` means "I want tools run" and
`end_turn` means "I'm done"; checking for tool_use blocks is equivalent here.)

**Iteration cap.** `max_iterations = 10` in module 1 and `5` in the capstone. Without a cap, a
confused model could call tools forever and burn money. Hitting the cap is a safety net, not a
normal exit.

**Every tool result must be answered.** Each `tool_use` block has an `id`; the next user
message must contain a `tool_result` with that `tool_use_id`, or the API rejects the request.
That is why the code builds `tool_results` while iterating over `tool_use_blocks`.

**Where hooks run.** The `PostToolUse` hook runs *after* the tool executes and *before* the
result is appended to `messages`, so the model sees the hook-corrected result. In module 1
the `DraftFormattingHook` only changes `draft_response` results; for other tools it returns the
result untouched.

**Tools can themselves call the model.** In module 1's live mode each tool executor
(`classify_ticket`, `route_ticket`, `draft_response`) makes its own `messages.create` call with a
narrow system prompt and parses JSON. So one ticket involves an outer agent call plus nested
calls. The outer model decides *which tool and when*; the inner calls do the work.

**Subagents are tools too.** `escalate_to_specialist` is exposed as a tool; when the agent calls
it, code runs `run_specialist_classifier`, a separate model call with a different, richer prompt.
The result overrides the earlier classification.

### 3.4 The mock loop

`MockAgentLoop.process_ticket` reproduces the *same sequence* deterministically:

```
classify -> (if ambiguous or confidence < 0.7: specialist overrides classification)
         -> route -> draft -> PostToolUse hook
```

and records each call in `tool_calls_log`. It exists so the pipeline can run, be traced
(module 4) and be tested with no API. It encodes the behaviour we *expect* from a good model; it
does not discover anything.

### 3.5 The capstone's loop is hybrid

[capstone/agent/orchestrator.py](capstone/agent/orchestrator.py) wraps an agentic core in fixed
workflow steps (section 12). Its live loop `_run_live_agent` differs from module 1's in three
ways: it caps at 5 iterations, it returns the *last* tool name and result it saw, and the
formatting hook and content policy run once on the final text rather than on each tool result.

---

## 4. Module 1 — Workflow vs. agent

Goal: build support-ticket triage twice (a fixed workflow and an agent), add a hook, delegate
ambiguous tickets to a subagent, and rebuild one piece with an agent framework.

### 4.1 Shared types — [shared.py](1_agents_and_workflows/shared.py)

- `Category`, `Priority`, `Team` are `str` enums: JSON-serializable and validated.
- `ClassificationResult`, `RoutingResult`, `DraftResponse`, `TicketResult` are Pydantic models.
  `confidence` is constrained to `0.0–1.0` with `Field(ge=0, le=1)`.
- Both implementations return the same `TicketResult`, so `run_comparison.py` can diff them
  field by field instead of comparing strings.
- `enforce_formatting()` applies `FORMATTING_RULES` deterministically: add a "Hi {name}," greeting
  if missing, split paragraphs over 80 words, append "Best regards, Support Team" if missing,
  collapse blank lines.

### 4.2 Test data — [tickets.py](1_agents_and_workflows/tickets.py)

20 tickets (15 clear-cut, 5 ambiguous) each with a `ground_truth` dict (category, priority,
is_ambiguous). Ground truth is what makes evaluation possible later (module 4).

### 4.3 The workflow — [workflow/pipeline.py](1_agents_and_workflows/workflow/pipeline.py)

```
classify(ticket) -> route(ticket, classification) -> draft_response(...) -> enforce_formatting
```

`run_pipeline` calls the three functions in order. Each step is exactly one model call with its
own system prompt, and each returns a validated Pydantic object (`json.loads` then
`ClassificationResult(**data)`).

Why: the sequence never changes, so there is nothing for a model to decide. The cost is exactly
three calls per ticket, each step is unit-testable, and failures are easy to locate. The weakness
is rigidity: it cannot re-classify or branch.

### 4.4 The agent — [agent/](1_agents_and_workflows/agent/)

| File | Role |
|------|------|
| `tools.py` | JSON-Schema definitions (`TOOL_DEFINITIONS`) and executors (`TOOL_EXECUTORS`) for `classify_ticket`, `route_ticket`, `draft_response`, `escalate_to_specialist` |
| `runner.py` | the agent loop (live) and `MockAgentLoop` (mock), plus `process_ticket` and `run_all` |
| `hooks.py` | `DraftFormattingHook` (PostToolUse) and `create_hooks()` |
| `subagent.py` | specialist classifier for ambiguous tickets |

`AGENT_SYSTEM_PROMPT` tells the model the usual order (classify, escalate if confidence < 0.7 or
ambiguous, route, draft) but explicitly allows deviating. That permission is what makes it an
agent rather than a scripted chain.

`process_ticket` runs the live loop when a client exists; on any API error it prints a notice and
falls back to the mock loop. It then coerces the raw dicts into Pydantic models, with a defensive
second attempt (`Category(...)` etc.) if validation fails.

### 4.5 Why a hook, not a prompt instruction

`DraftFormattingHook.__call__(tool_name, tool_input, tool_result)` ignores everything except
`draft_response`. For drafts it parses the result into `DraftResponse`, calls `enforce_formatting`,
records what changed (`_diff_summary`), and returns the corrected dict.

A prompt that says "always greet and sign off" works most of the time. A hook works every time and
frees the model to focus on content. The function is pure (no API calls), so it is unit-testable.
The hook mirrors the Claude Agent SDK's `PostToolUse` concept, implemented as a plain callable
because this repo builds its loop directly on the Messages API rather than on the Agent SDK.

### 4.6 Why a subagent, not inline logic

`run_specialist_classifier` is a separate model call with a prompt containing few-shot examples of
tricky tickets and a "list all topics, find the primary action" decision process.

- **Prompt focus:** putting that into the main agent's prompt would dilute it for the ~75% of tickets
  that are clear.
- **Independent evaluation:** you can measure the specialist on ambiguous tickets alone.
- **Conditional cost:** it is called only when confidence < 0.7 or `is_ambiguous` is true.
- **Replaceable:** it can use another model or temperature without touching the main agent.

### 4.7 PydanticAI — [pydantic_ai_component/classifier.py](1_agents_and_workflows/pydantic_ai_component/classifier.py)

The classification step rebuilt with PydanticAI:
- `Agent(model, result_type=ClassificationResult, retries=2)` validates output against the model and
  retries on validation failure — replacing manual `json.loads` plus `try/except`.
- `@agent.tool` generates a JSON schema from the function signature and docstring.
- `RunContext[ClassifierDeps]` injects the ticket into tools (dependency injection).
- Without an API key it uses PydanticAI's built-in `"test"` model.

Trade-off recorded in the module docstring: less boilerplate and built-in validation retries, but
less visibility into the exact messages and an extra dependency.

### 4.8 Mock vs live here

The workflow's mock classification uses keyword matching and, for convenience, copies priority from
the ticket's `ground_truth`. The agent's mock uses keyword rules in `tools.py`. Both produce the same
output shapes as live mode.

---

## 5. Module 2 — DocuQuery (application and integration)

Goal: a real API around Claude — upload a document, ask questions, stream answers, cache the
document, manage sessions, pin configuration.

### 5.1 Request flow

```
POST /api/v1/documents/upload   -> parse_document() -> SessionManager.create_session() -> session_id
POST /api/v1/sessions/{id}/ask  -> ask_question()    -> StructuredAnswer (+usage, cached flag)
POST /api/v1/sessions/{id}/ask/stream -> ask_question_stream() -> SSE "data: <chunk>\n\n" ... [DONE]
```

Files in [2_applications_and_integration/app/](2_applications_and_integration/app/):

| File | Responsibility |
|------|----------------|
| `main.py` | FastAPI app, CORS (open, "internal tool"), mounts router under `/api/v1`, root info endpoint |
| `routes.py` | endpoints; 404 for missing/expired sessions; `QuestionRequest` limits question to 1–2000 chars |
| `document.py` | splits text into named sections using header regexes (`=== Name ===`, `Section N:`, `Article N:`, ALL-CAPS lines); falls back to one "Full Document" section |
| `session.py` | `Session`, `SessionManager` and the lifecycle rules |
| `claude_client.py` | prompt building, streaming, caching, structured-answer parsing, mock mode |
| `models.py` | Pydantic schemas (`Citation`, `StructuredAnswer`, `QuestionResponse`, ...) |
| `config.py` | YAML + environment config accessors |

### 5.2 Prompt caching in this app

`_build_system_prompt` returns two system blocks when caching applies:

```
[ {text: system instructions},
  {text: "Here is the document ...", cache_control: {"type": "ephemeral"}} ]
```

The document is in the **system prompt**, not the user messages, and is the last stable block; the
conversation (`messages`) is the variable suffix. That ordering is required because caching matches
prefixes. Caching is skipped when it is disabled in `config.yaml` or the document is shorter than
`min_document_length` (500 characters). The API enforces its own minimum cacheable length, so short
documents may not produce cache hits even above the config threshold.

The `usage` object reports `cache_creation_input_tokens` (first call) and `cache_read_input_tokens`
(later calls). `routes.ask` sets `cached = usage["cache_read_input_tokens"] > 0`.

### 5.3 Streaming

`_stream_live` uses `with client.messages.stream(...) as stream` and yields each piece of
`stream.text_stream`. After the stream ends it reads `stream.get_final_message()` for usage, records
the turn in the session, and triggers summarization if needed. It is a Python **generator that also
returns a value** (the usage dict): `ask_question` drives it manually and reads `StopIteration.value`,
while `ask_stream` wraps each chunk as an SSE event and sends `[DONE]` at the end.

### 5.4 Session design (the five documented decisions)

From the docstring in `session.py`:

1. **Create:** one session per document upload, identified by a UUID.
2. **Persist:** in-memory dict, written on every turn (swap-in point for Redis).
3. **Summarize:** when estimated history tokens (`chars // 4`) exceed `summarize_threshold` (40,000),
   turns older than the last 3 collapse into one summary string. The summary is a concatenation of
   truncated Q/A pairs, not a model-written summary.
4. **Restart:** explicit `POST /sessions/{id}/reset`; uploading a new document makes a new session.
5. **Expire:** idle timeout (30 min) checked lazily on access (`get_session` deletes expired sessions).

Known, documented limits (see `code_review.md`): the store is not thread/process-safe, upload size is
unlimited, and expiry is not a background job.

### 5.5 Structured answers

`_parse_to_structured` builds `StructuredAnswer` from the raw text: a section counts as cited if its
name appears in the answer; confidence is `HIGH` for two or more citations, `MEDIUM` for one, `LOW`
for none, or `NOT_FOUND` if the text says the information is not covered. Follow-up suggestions come
from a small topic table. So the schema is validated by Pydantic, but citations and confidence are
derived heuristically, not produced by the model as JSON.

### 5.6 Configuration management — [config.yaml](2_applications_and_integration/config.yaml)

- `model.name` pins an explicit model ID; `get_model_name()` returns
  `CLAUDE_MODEL` or `ANTHROPIC_MODEL` environment variable if set, otherwise the YAML value. Keep
  those variables unset when the pin must hold.
- `prompts.system_v1` / `system_v2` with `created` and `note`, selected by `active_version`. Prompt
  changes are therefore visible diffs in version control.
- `session` and `cache` blocks hold the lifecycle and caching settings.

### 5.7 Batches API decision

The README argues the Message Batches API does not fit: interactive latency, multi-turn dependency
(turn N+1 needs the answer to N), streaming, and mutable session state. Batches fit offline work
such as nightly evaluation of many questions at a discount.

### 5.8 Tests and validation

`tests/test_models.py` (16 tests) validates the schemas. `run_validation.py` checks that the app
loads, routes are registered, config loads, models validate, the client resolves, and sample
documents exist — this is what `main.py` runs for module 2 (it does not start the server).

---

## 6. Module 3 — Claude Code configuration

Goal: configure Claude Code deliberately for a repository. The files in `3_claude_code/` are
**templates** you copy to the repository root to activate.

### 6.1 CLAUDE.md hierarchy

CLAUDE.md files are instructions Claude Code loads into context.

- A project-level `CLAUDE.md` at the repository root loads at session start.
- A `CLAUDE.md` inside a subdirectory loads on demand, when Claude reads files in that directory.
- Rules combine: directory rules supplement project rules.
- `/memory` lists the loaded files and `/context` shows what occupies the context window.

[3_claude_code/CLAUDE.md](3_claude_code/CLAUDE.md) holds project-wide conventions (build and test
commands, coding standards, environment). `sample_subfolder/CLAUDE.md` holds agent-specific rules
(hooks, subagents, naming) meant to be copied to `1_agents_and_workflows/CLAUDE.md`.

Why CLAUDE.md rather than prompts: a typed prompt disappears on `/clear`; CLAUDE.md is re-read every
session, so the project context is not re-explained each time.

### 6.2 Settings and permissions — `.claude/settings.json`

```json
{ "permissions": {
    "allow": ["Bash(uv sync)", "Bash(uv run *)", "Bash(pytest *)", "Bash(git log *)", ...],
    "deny":  ["Read(./.env)", "Read(./.env.*)", "Read(1_agents_and_workflows/.env)"] } }
```

`allow` pre-approves safe, repeatable commands. `deny` is a hard block the model cannot talk its way
around. `settings.local.json` is for personal overrides (an empty example here).

### 6.3 Custom slash command

`.claude/commands/summarize-changes.md` is a markdown prompt invoked as `/summarize-changes`: it
tells Claude to read `git log` and `git diff --stat`, then produce a structured summary. A file
instead of retyping the prompt makes it repeatable, consistent and shareable.

### 6.4 Headless mode

`claude -p "prompt"` runs once without an interactive session and prints the result;
`--output-format json` gives machine-readable output. `scripts/headless_summary.py` (and the
PowerShell twin) run it through `subprocess`, capture stdout, and save to `scripts/output/`. This is
the building block for CI jobs, cron tasks and scripts.

### 6.5 Validator

`validate_setup.py` (rich-formatted) checks that the templates exist and have expected sections,
that `settings.json` is valid JSON with allow/deny rules, that commands exist, and reports whether
live mode is available. A missing API key is reported as mock mode, not as a failure. With
`--headless` it also runs `claude --version` and a one-line `claude -p`.

---

## 7. Module 4 — Evals, tracing and debugging

Goal: take a working agent, break it in two different layers, and show how traces tell you which
layer is at fault and therefore which kind of fix to apply.

### 7.1 The two deliberate bugs

| | Bug 1 | Bug 2 |
|---|-------|-------|
| Layer | Integration (code) | Model output (prompt) |
| Where | `broken_app/tools.py` `execute_route_ticket`: `is_ambiguous = False` | `broken_app/runner.py` `AGENT_SYSTEM_PROMPT`: "determine how important each ticket seems" instead of a rubric |
| Symptom | Ambiguous tickets reach the router flagged ambiguous but are not escalated | Priorities too low (billing, technical, account tickets rated `medium`) |
| Correct fix | Change code: `args.get("is_ambiguous", False)` | Change prompt: add the URGENT/HIGH/MEDIUM/LOW rubric |

The lesson is that both show up as "routing is wrong", but editing the wrong layer (patching
priorities in code, or "prompting harder" for a hardcoded value) does not fix them.

### 7.2 How the apps differ

`fixed_app/` is the same code as `broken_app/` except for the two fixes: the one line in
`tools.py` and the prompt text in `runner.py`. `hooks.py` and `subagent.py` are identical.

### 7.3 The simulated model — [mock_model.py](4_eval_testing_and_debugging/mock_model.py)

In mock mode there is no real model, so `mock_model.py` simulates one whose behaviour depends on the
**system prompt**:

- If `AGENT_SYSTEM_PROMPT` contains the `Priority Rubric` marker, the simulated model assigns
  priority from the rubric (`rubric_priority`: deadline/blocking → urgent; money/GDPR/crash → high;
  invoice-copy/feature → low; else medium).
- Otherwise it falls back to `vague_prompt_classification`: everything except feature requests is
  `medium`.

`MockAgentLoop._judge_priority` applies that behaviour to both the first classification and the
specialist result, before they are logged. Because it keys off the prompt text, changing only the
prompt changes the outcome — which is the property the exercise needs. It encodes the *expected*
effect of a vague prompt; it does not prove a real model behaves this way.

### 7.4 Tracing — [tracer.py](4_eval_testing_and_debugging/tracer.py)

For each ticket the tracer runs the mock agent, stores every tool call (`step`, `tool_name`, inputs,
outputs), and runs `analyze_ticket_trace`, which flags:

| Anomaly | Meaning |
|---------|---------|
| `DROPPED FIELD` | classify output has `is_ambiguous=True` but the route input does not |
| `IGNORED FIELD` | route input has `is_ambiguous=True` yet the router returned `escalate=False` — the tool received the signal and did not act on it |
| `PRIORITY MISMATCH` | classify output priority differs from the route input priority |
| `WRONG PRIORITY` | final priority differs from the ticket's ground truth |
| `MISSING ESCALATION` | ground truth says ambiguous but routing did not escalate |

Aggregated counts (`priority_mismatches`, `escalation_failures`, `dropped_fields`, `ignored_fields`)
go into the trace summary. Bug 1 appears as `IGNORED FIELD` (the runner does pass the field, so there
is no `DROPPED FIELD`); Bug 2 appears as `WRONG PRIORITY`.

### 7.5 Scripts and diagnosis

- `run_broken.py` — traces the broken app and prints signals for each bug.
- `run_fixed.py` — traces the fixed app and verifies zero dropped/ignored fields, zero priority
  mismatches, and no missing escalations.
- `run_comparison.py` — side-by-side metrics and per-ticket diffs, saved to `output/comparison.md`.
- `diagnosis/hypothesis.md` — hypotheses written before looking at code.
- `diagnosis/trace_analysis.md` — what the traces showed and which hypotheses were confirmed. The
  first hypothesis guessed the field was *dropped* in data passing; the trace showed it was passed
  correctly and *ignored* by the router.

Typical results: broken app 10 priority mismatches and 3 missing escalations; fixed app 0 and 0.

### 7.6 Why this is a good debugging method

Instrument each step's inputs and outputs, then compare step N's output to step N+1's input and
compare final outputs to ground truth. If data is correct going in and wrong coming out of the same
function, the bug is in that function's code. If data is passed through unchanged but quality is
wrong, suspect the prompt or model.

---

## 8. Module 5 — Model selection and optimization

Goal: choose a model and an optimization for three workloads using measured cost, latency and quality.

### 8.1 Building blocks

- [models.py](5_model_selection_and_optimization/models.py): `ModelId` (Haiku 4.5, Sonnet 4.6),
  `PRICING` ($/million tokens: input, output, cache write, cache read), `MODELS` metadata, and
  `calculate_cost`:

  ```
  cost = input/1e6*in_price + output/1e6*out_price + cache_write/1e6*write_price + cache_read/1e6*read_price
  ```

  Haiku: 1.00 / 5.00 / 1.25 / 0.10. Sonnet: 3.00 / 15.00 / 3.75 / 0.30.

- [tracker.py](5_model_selection_and_optimization/tracker.py): `MetricsTracker.track(call_id, model, task)`
  is a context manager that times the call (`perf_counter`), accepts token counts via `set_tokens`,
  computes cost, and aggregates per-task summaries (average latency, throughput, total cost).

### 8.2 Task A — high-volume classification (Haiku vs Sonnet)

50 labelled emails, 5 sentiment categories, accuracy bar of 85% fixed *before* running. The
reasoning: a structurally simple mapping from text to one of five labels does not benefit from a
larger model, and Haiku is cheaper and faster. In mock mode both models share one keyword
classifier, so equal accuracy is by construction; the benchmark shows the comparison harness (accuracy,
throughput, cost) rather than a real model difference.

### 8.3 Task B — complex reasoning (extended thinking)

Five multi-step problems scored on a 10-point rubric, comparing "fast" (no thinking,
`max_tokens=4096`) with extended thinking (`budget_tokens=10000`, `max_tokens=16000`). The live helper
extracts the `text` block as the answer and records thinking tokens (from `usage` when reported,
otherwise estimated from the thinking text). Reasoning: multi-constraint problems benefit from
deliberation, and they are low-volume enough that the higher cost and latency are acceptable.

### 8.4 Task C — long-document summarization with caching

Three long documents, each summarized and then questioned, run once with `cache_control` on the
document and once without. Worked example for a 2,000-token document on Sonnet:

| | Cost per call |
|---|---------------|
| No caching | 2,000 × $3.00/MTok = $0.0060 |
| Cache write (first call) | 2,000 × $3.75/MTok = $0.0075 |
| Cache read (later calls) | 2,000 × $0.30/MTok = $0.0006 |

The write costs 25% more once; every later call is 90% cheaper on the document portion.

### 8.5 What actually runs

The runners (`run_all.py`, `task_*/run.py`) always use mock mode with simulated token counts and
real prices. The modules also contain live helpers (`classify_email_live`,
`solve_fast_mode_live`, `solve_extended_thinking_live`, `summarize_live_cached`,
`summarize_live_uncached`) that take a client, but the bundled runners never pass one.
`justifications.md` is the written justification per task.

---

## 9. Module 6 — Prompt and context engineering

Goal: keep a long conversation reliable and well-formatted. A good prompt carries turn 1; by turn 20
context bloat and instruction dilution degrade output.

### 9.1 System prompt design — [system_prompt.py](6_prompt_and_context_engineering/system_prompt.py)

- **Strict output contract:** JSON with `summary` (≤ 50 words), `details`, `sources` (list),
  `confidence` (high|medium|low), `follow_up` (string or null); no fences, no commentary.
- **Few-shot examples:** three examples on *vague* questions, the hardest input type.
- **Instruction anchoring:** the key format rules appear at the start *and* the end of the prompt, to
  resist the model "forgetting" them as context grows.

### 9.2 Context management — [context_manager.py](6_prompt_and_context_engineering/context_manager.py)

`ContextManager` stores `Message` objects tagged with `turn_number` and `is_tool_output`, and builds the
API messages differently by turn count:

| Stage | Turns | Behaviour |
|-------|-------|-----------|
| 1 Full | 1–8 | send everything |
| 2 Prune | 9–15 | tool outputs over 100 tokens are replaced by their first 30 and last 20 words |
| 3 Compact | 16+ | turns older than the last 8 are replaced by one summary block (first sentence of each user message) plus a fixed assistant acknowledgement; recent tool outputs are still pruned |

Every turn records `TurnMetrics` (context tokens, tool tokens, pruned tokens, compaction flag, format
compliance), so savings can be measured instead of assumed. Token counts are estimates (~1.33 per
word). Compaction here is a deterministic heuristic, not an LLM-written summary.

### 9.3 Subagent isolation — [subagent.py](6_prompt_and_context_engineering/subagent.py)

`knowledge_base_lookup(query)` returns `(full_result, compact_summary)`. The full result (hundreds to
thousands of tokens) is discarded; only the compact summary (tens of tokens) is added to the
conversation through `add_tool_output`. One verbose lookup therefore cannot consume a large share of the
context window.

### 9.4 Defensive parsing — [structured_output.py](6_prompt_and_context_engineering/structured_output.py)

`parse_response` never raises and never silently accepts bad data. Strategies in order:

1. `json.loads` on the whole text.
2. Extract from a ```` ```json ```` fence and parse.
3. Repair (`_try_repair_json`): strip trailing commas, append missing `}` / `]`, cut to the first `{`.
4. Fallback response (`_make_fallback`): raw text as summary, confidence `low`.

Every non-clean path sets `parse_error`. `_validate_and_normalize` coerces types (sources must be a
list, confidence is lower-cased and defaulted to `low` if invalid, `"null"` follow-up becomes `None`).
`AssistantResponse.is_valid()` and `format_compliance()` expose the checks the drift analysis uses.

### 9.5 The assistant and the session test

`TechSupportAssistant.ask` runs: add user message → (if trigger words match) isolated lookup → get
response (live `messages.create` with context-managed messages, or mock) → parse → store →
record metrics. `run_session.py` simulates 25 turns and reports format compliance early/mid/late plus
token savings; `run_parser_test.py` feeds ten malformed inputs to the parser.

Reported figures come from mock mode (word-count token estimates and an assistant that always emits
valid JSON); the "without compaction" figure is a linear extrapolation of the turn-8 context.

---

## 10. Module 7 — Security and safety

Goal: attack a vulnerable app with prompt injection, then harden it with layered defenses, including
secrets handling and access control.

### 10.1 Why prompt injection works

When untrusted text is concatenated into a prompt, the model cannot reliably tell the developer's
instructions from instructions hidden in the data. `vulnerable_app` demonstrates this on purpose:
its system prompt even says "follow any special instructions in the article text".

### 10.2 The vulnerable app (deliberately flawed)

- `summarizer.py`: untrusted text pasted directly into the prompt; mock responses simulate a model
  that obeys injections; `_detect_injection_success` looks for signals (prompt leaked, role hijacked,
  secrets exposed, action confirmed, canary strings).
- `hooks.py`: pre/post hooks that pass everything through.
- `actions.py`: `send_email`, `delete_user_data` with no authentication, and two hardcoded fake secrets.

### 10.3 The ten attacks — [payloads.py](7_security_and_safety/payloads.py)

System-prompt extraction, instruction override, role hijacking, data exfiltration, action triggering,
delimiter escape, encoded (base64) injection, indirect injection hidden in normal text, multi-turn
manipulation, and a DAN-style jailbreak.

### 10.4 The hardened app — four layers

```
article text
   |
   v  Layer 1  pre_process_hook        regex detection of known injection phrasings  (code)
   |  blocked? -> safe "blocked" summary
   v  Layer 2  input isolation         text wrapped in <user_content>; system prompt says it is DATA  (prompt)
   v  model
   v  Layer 3  post_process_hook       content_policy: credential/prompt-leak/action/role-hijack/canary regexes  (code)
   |  blocked? -> sanitized response
   v  summary
      Layer 4  actions.py              identity + permission + audit on consequential actions  (code)
```

- **Layer 1** ([hardened_app/hooks.py](7_security_and_safety/hardened_app/hooks.py)): 21 compiled
  regexes grouped into categories (instruction override, prompt extraction, role hijack,
  exfiltration, action trigger, delimiter escape, encoded payload, jailbreak, impersonation). It
  returns `allowed`, `reason`, and the detections.
- **Layer 2** (`_build_prompt` and `SYSTEM_PROMPT`): delimiters plus explicit safety rules. This layer
  is probabilistic: it works only if the model follows the rule.
- **Layer 3** ([content_policy.py](7_security_and_safety/hardened_app/content_policy.py)): independent
  of Layer 1, checks the *output*. It is the safety net for an injection no regex recognised.
- **Layer 4** ([actions.py](7_security_and_safety/hardened_app/actions.py)): a token maps to a user with
  a role and permission set (`token_admin_001` may delete data; `token_user_042` may only send email).
  Every attempt, allowed or blocked, is written to an audit log that records *that* a token was
  supplied, never the token itself. `get_system_config` masks API keys. Secrets come from
  `os.environ`.

### 10.5 Secrets audit — [secrets_audit.py](7_security_and_safety/secrets_audit.py)

Scans both apps' source line by line with regexes for hardcoded secrets (one finding per line) and for
good practice (`os.environ`/`dotenv`, masking). Result: the vulnerable app has 2 hardcoded secrets;
the hardened app has none.

### 10.6 What the numbers do and do not prove

All ten attacks are stopped by Layer 1, because those patterns were written for those payloads. That
shows the hook covers the *known* attacks, not unknown phrasings. [layer_checks.py](7_security_and_safety/layer_checks.py)
therefore tests each layer with its own input: a paraphrased injection passes Layer 1 (documenting its
limit), Layer 2's structure is verified, four simulated compromised outputs are blocked by Layer 3, and
unauthenticated and under-privileged callers are blocked by Layer 4 while an admin is allowed, with the
audit log verified.

The takeaway: regex detection is a useful first filter but easy to evade; the controls that actually
bound damage are the output policy and, above all, access control on consequential actions.

---

## 11. Module 8 — Tools, Skills and MCP

Goal: implement one capability (an internal inventory lookup) three ways and compare them honestly.

Shared pieces: `inventory_data.py` (15 products, lookup/search/low-stock helpers) and
`error_model.py` (structured errors `{error: {category, retryable, description}}` with categories
`not_found`, `invalid_input`, `internal_error`).

### 11.1 Custom tool (Anthropic `tool_use`)

[custom_tool/tool_definitions.py](8_tools_and_MCPs/custom_tool/tool_definitions.py) holds three JSON
Schema tools whose descriptions say *when* to use each (SKU known → lookup; name known → search;
reorder question → low stock). `tool_executor.execute_tool` dispatches by name, validates inputs, and
wraps unexpected exceptions into `internal_error` (retryable). `run_agent_query` is a mock single-pass
"agent" that picks a tool by keyword and formats the result. In a real application the model would make
the tool choice from these schemas.

Pros: fastest to build, no extra dependencies, runs in-process. Cons: tied to your application; another
team must copy the code.

### 11.2 Skill

[skill/SKILL.md](8_tools_and_MCPs/skill/SKILL.md) has YAML frontmatter (`name`, `description`) and
instructions; `scripts/inventory_skill.py` is a CLI that prints JSON (`lookup`, `search`, `low-stock`).
The test runner invokes the script through `subprocess`; Claude Code would discover the skill from its
description and run the script itself. The description is what lets the agent decide when the skill is
relevant.

Pros: reusable across projects within Claude Code, process-isolated. Cons: only within that ecosystem.

### 11.3 MCP server

[mcp_server/server.py](8_tools_and_MCPs/mcp_server/server.py) uses the MCP SDK's server class
(`MCPServer`, with fallbacks to `FastMCP` imports) and exposes:

| MCP concept | Item | Controlled by |
|-------------|------|---------------|
| Tools | `inventory_lookup`, `inventory_search`, `inventory_low_stock` | the model |
| Resource | `inventory://catalog` (read-only catalog) | the application |
| Prompt | `inventory_check` (template) | the user |

Decorators generate the tool schemas from Python type hints and docstrings. Transport is JSON-RPC over
stdio. [client.py](8_tools_and_MCPs/mcp_server/client.py) shows the protocol flow: start the server as a
subprocess with `stdio_client`, `ClientSession.initialize()`, then `list_tools` / `list_resources` /
`list_prompts`, then `call_tool`, `read_resource`, `get_prompt`.

Pros: any MCP-compatible client in any language can use it without copying code; supports resources and
prompts. Cons: slowest to build and needs the SDK and an extra process.

### 11.4 Equivalence check

`run_all.py` runs the same five queries through all three and verifies identical results (including the
same structured error for an unknown SKU). Because all three call the same data layer and error model,
identical results are expected; the value is the comparison of interfaces. `comparison.md` states the
trade-offs and the recommendation: custom tool for a single-team lookup, MCP when a second team,
non-Python client or shared reference data appears.

---

## 12. Capstone — the integrated support assistant

A customer-support assistant that answers product questions, looks up orders and accounts, escalates
unresolved issues, defends against injection, routes models by task, and manages long conversations.

### 12.1 Request lifecycle — `process_message` in [orchestrator.py](capstone/agent/orchestrator.py)

```
user message
 1. pre_process_check            regex guardrails (security/guardrails.py)    -> blocked? return canned refusal
 2. context_manager.add_user_message                                         (context/manager.py)
 3. router.classify_intent -> get_config -> model_name                       (models/router.py)
 4. tool selection:
      live  : _run_live_agent  (model calls tools in a loop, max 5 iterations)
      mock  : _mock_select_tool (keywords) -> TOOL_EXECUTORS[tool](args)
 4.5 specialist subagent        only if no tool was chosen and the message is not a greeting
                                -> may convert to an escalation ticket
 5. formatting hook             greeting / sign-off / paragraph length
 6. post_process_check          content policy on the final text
 7. context_manager records the assistant message and a truncated tool output
 8. cost_tracker.record_call    tokens ESTIMATED from word counts, cost from the pricing table
```

Steps 1, 5 and 6 are fixed workflow steps (always run, in code); steps 3–4 are the agentic core; the
combination is a hybrid by design: deterministic where behaviour must be guaranteed, flexible where
judgement helps.

### 12.2 Model routing — [models/router.py](capstone/models/router.py)

`TASK_CONFIGS` maps each `TaskType` to a model, token limit, temperature and a written justification:

| Task | Model | When |
|------|-------|------|
| `SIMPLE_LOOKUP` | Haiku | order/account/billing keywords |
| `CLASSIFICATION` | Haiku | FAQ keywords (return policy, warranty, ...) |
| `COMPLEX_REASONING` | Sonnet | everything else (default for unknown tasks) |
| `SPECIALIST` | Sonnet | ambiguous multi-intent analysis |

`classify_intent` is a fast keyword classifier, not an LLM call, so routing itself costs nothing. The
orchestrator takes the model name straight from the router; a `CLAUDE_MODEL` environment override must
not leak in, because it would send every task to one model.

### 12.3 Tools — [agent/tools.py](capstone/agent/tools.py)

`lookup_order`, `lookup_account`, `search_knowledge_base`, `escalate_to_human`, each with a JSON Schema
and an executor that returns structured results or `{error, error_type, suggestion}`. Order and account
data come from `data/orders.py` (10 orders, 5 accounts); articles from `data/knowledge_base.py`
(15 articles). `escalate_to_human` creates a ticket with ID, priority, reason and a customer message.

### 12.4 Guardrails — [security/guardrails.py](capstone/security/guardrails.py)

An adaptation of module 7's two code layers for customer messages: 21 input patterns (including a
base64-like pattern) in `pre_process_check`, and credential / prompt-leak / role-hijack / canary
patterns in `post_process_check`. Both return `allowed` plus details; the output check returns a
sanitized replacement on failure.

### 12.5 Context management — [context/manager.py](capstone/context/manager.py)

Module 6's manager with tighter thresholds because support turns are tool-heavy: prune after turn 6,
compact after turn 12, tool outputs over 80 tokens pruned, last 6 turns kept in full.

### 12.6 Formatting hook — [agent/hooks.py](capstone/agent/hooks.py)

`ResponseFormattingHook` applies the greeting / paragraph-length / sign-off rules to the final response
text.

### 12.7 Specialist subagent — [agent/subagent.py](capstone/agent/subagent.py)

Invoked for messages no tool matched. With a client it makes a Sonnet call with a prompt containing
intent categories and few-shot examples, asking for JSON (`primary_intent`, `all_intents`, `priority`,
`reasoning`, `should_escalate`); without one it uses a mock. If it says to escalate, the orchestrator
calls `escalate_to_human` with the specialist's reason and priority.

### 12.8 Knowledge-base MCP server — [data/mcp_server.py](capstone/data/mcp_server.py)

A standalone MCP server over the knowledge base (search tool and article catalog resource). The
orchestrator does **not** call it: the assistant's `search_knowledge_base` tool calls
`search_articles` directly. The server demonstrates the "shared reference data as MCP" design and can be
started separately.

### 12.9 Web app and CLI

[app.py](capstone/app.py) (FastAPI): chat UI at `/`, `POST /api/chat`, `/api/health`, `/api/stats`,
with an in-memory `{session_id: SupportSession}` store. [run_capstone.py](capstone/run_capstone.py)
provides `--interactive`, `--server`, and a default self-test that exercises the pipeline.

### 12.10 Evals and seeded bugs — [capstone/eval/](capstone/eval)

`eval_suite.py` defines 10 `EvalCase`s (4 core, 3 edge, 2 adversarial, 1 regression). Each case has a
user message and a list of assertion closures such as `_assert_tool_used`, `_assert_response_contains`,
`_assert_has_greeting`, `_assert_model_is("haiku")`. `run_evals.py` pushes each message through
`process_message` and reports pass/fail; the regression case first replays 14 earlier turns to test long
conversations.

`seeded_bugs.py` documents two deliberate bugs:

- **Bug 1 (integration):** an environment variable overriding the router's choice in the orchestrator.
  It is fixed. If reintroduced, EVAL-001 (which asserts Haiku served an order lookup) fails, and
  `verify_bug_1_is_fixed()` — which sends a lookup through the real orchestrator with `CLAUDE_MODEL` set
  — also fails.
- **Bug 2 (model output):** `execute_escalate_to_human` does not normalize an uppercase priority
  (`"URGENT"`), so the urgent response-time branch is skipped. It is left in place; the mock never
  produces uppercase so the 10 cases pass, and `verify_bug_2_is_fixed()` detects it. The runner reports
  it as `DETECTED (expected)` and the process exit code treats that as the intended outcome.

---

## 13. Concept glossary

| Term | Meaning in this repository |
|------|----------------------------|
| **Agent** | A loop in which the model chooses tools and ordering until it stops requesting tools |
| **Workflow** | A fixed code-controlled sequence of model calls |
| **Tool / tool use** | A function described by JSON Schema that the model can request; your code runs it |
| **Tool result** | Your code's answer, sent back in a `tool_result` block tied to the `tool_use` id |
| **Hook** | Code run at a defined point (here after a tool) that enforces a rule deterministically |
| **Subagent** | A separate, narrowly scoped model call (own prompt) invoked by the main agent |
| **System prompt** | Instructions framing the whole conversation, separate from messages |
| **Few-shot examples** | Worked examples inside a prompt to steer format and edge-case handling |
| **Instruction anchoring** | Repeating key rules at the start and end of a long prompt |
| **Prompt caching** | Reusing a stable prompt prefix at a reduced price via `cache_control` |
| **Cache write / read** | First-time storage (premium price) / later reuse (about 10% of input price) |
| **Streaming / SSE** | Delivering output as it is generated / the HTTP format (`data: ...\n\n`) used here |
| **Extended thinking** | Model reasoning before answering, billed as output tokens |
| **Context window** | Maximum tokens per call; why pruning and compaction exist |
| **Pruning** | Replacing bulky tool outputs with short summaries |
| **Compaction** | Replacing old turns with one summary block |
| **Structured output / defensive parsing** | Requiring JSON and parsing it so malformed output never crashes or silently corrupts data |
| **Prompt injection** | Instructions hidden in untrusted data that try to steer the model |
| **Guardrail** | A check on input or output; deterministic (code) or probabilistic (prompt) |
| **Defense in depth** | Independent layers so one failure is not fatal |
| **Least privilege / RBAC** | Tokens map to roles with only the permissions they need (module 7 actions) |
| **Audit log** | Record of every attempted sensitive action, without secrets |
| **Model routing** | Choosing a model per task type by cost, latency and capability |
| **Eval / ground truth** | Test cases with known correct answers used to measure quality |
| **Trace** | Per-step record of inputs and outputs used to localise a bug |
| **Seeded bug** | A bug planted on purpose to test whether evals and diagnosis catch it |
| **MCP** | Model Context Protocol: a standard for servers that expose tools, resources and prompts to any client |
| **Resource / prompt (MCP)** | Read-only data addressed by URI / a reusable prompt template |
| **Skill** | A folder with `SKILL.md` (name + description) and optional scripts Claude Code can load when relevant |
| **CLAUDE.md** | Persistent project instructions loaded by Claude Code |
| **Headless mode** | `claude -p` non-interactive execution for automation |
| **Mock mode** | Deterministic stand-in for the model so everything runs with no API key |

---

## 14. What is simulated, what is real, what is deliberate

### 14.1 Simulated in mock mode

| Area | What is simulated |
|------|-------------------|
| Model decisions | Keyword rules replace the model's classification, routing, tool choice and drafting |
| Module 4 prompt effect | `mock_model.py` encodes the expected effect of a vague vs rubric prompt |
| Token counts | Estimated from text length unless a live call reports `usage` |
| Module 5 results | Accuracy equal by construction; costs from real prices with simulated tokens; the bundled runners never call the API |
| Module 6 figures | Mock assistant always emits valid JSON; "no compaction" figure is extrapolated |
| Module 7 vulnerable/hardened responses | Scripted to show an obedient vs a safe model |
| Module 8 | No live path; the custom-tool "agent" is one keyword-selected call |
| Capstone costs | Estimated from word counts even in live mode |
| Capstone knowledge base | Searched by a local function, not through the MCP server |

### 14.2 Real regardless of mode

Pydantic validation, the hooks, regex guardrails, content policy, access control and audit logging, the
context manager, the defensive parser, the session lifecycle, the FastAPI endpoints, the secrets audit,
cost formulas, the tracer, and the eval harness all run as real code.

### 14.3 Deliberate flaws (do not "fix" these)

| Where | Flaw | Purpose |
|-------|------|---------|
| `4_.../broken_app/tools.py` | `is_ambiguous = False` | integration-layer bug to diagnose |
| `4_.../broken_app/runner.py` | prompt without priority rubric | model-output problem to diagnose |
| `7_.../vulnerable_app/` | no isolation, no-op hooks, hardcoded fake secrets, no access control | attack target |
| `capstone/agent/tools.py` | uppercase priority not normalized | seeded Bug 2, detected by `verify_bug_2_is_fixed()` |
| `2_.../code_review.md` | issues 2–4 noted but not fixed | documented review findings |

### 14.4 Known limitations worth knowing

- Module 2's session store is in-memory and not thread-safe; session summaries are concatenations.
- Regex guardrails (modules 7 and capstone) only recognise known phrasings; they are a first filter, not
  a complete defense.
- Module 3's configuration files are templates; they take effect only after being copied to the
  repository root.
- `5_.../justifications.md` and some prose docstrings mention older model names and prices than
  `models.py`; the code (`models.py`) is authoritative.

---

## Appendix A — Where each concept is used

Use this as an index: pick a concept, then jump to where it is implemented and where it is exercised.
"Mock" means the deterministic stand-in used when no API key is set.

### A.1 Agents, tools and delegation

| Concept | Implemented in | Used / demonstrated by |
|---------|----------------|------------------------|
| **Agentic loop (live)** | [runner.py:158](1_agents_and_workflows/agent/runner.py:158) `run_agent_loop_live` (cap 10 at :182); [orchestrator.py:476](capstone/agent/orchestrator.py:476) `_run_live_agent` (cap 5 at :485) | Module 1 `run_comparison.py`; capstone `process_message`, eval suite, web app |
| **Agentic loop (mock)** | [runner.py:81](1_agents_and_workflows/agent/runner.py:81) `MockAgentLoop`; [broken_app/runner.py:62](4_eval_testing_and_debugging/broken_app/runner.py:62) and `fixed_app/runner.py`; [tool_executor.py](8_tools_and_MCPs/custom_tool/tool_executor.py) `run_agent_query` (single pass) | Module 4 tracer replays it to build traces; module 1 and capstone fall back to it on API errors |
| **Workflow (fixed chain)** | [pipeline.py](1_agents_and_workflows/workflow/pipeline.py) `run_pipeline`: classify → route → draft | Module 1 comparison against the agent |
| **Tool definitions (JSON Schema)** | [agent/tools.py:39](1_agents_and_workflows/agent/tools.py:39); [capstone/agent/tools.py:39](capstone/agent/tools.py:39); [tool_definitions.py:11](8_tools_and_MCPs/custom_tool/tool_definitions.py:11) | Passed as `tools=` in the live loops; module 8 compares them with a Skill and an MCP server |
| **Tool executors / dispatch** | [agent/tools.py:269](1_agents_and_workflows/agent/tools.py:269) `TOOL_EXECUTORS`; [capstone/agent/tools.py:219](capstone/agent/tools.py:219); [tool_executor.py:21](8_tools_and_MCPs/custom_tool/tool_executor.py:21) `execute_tool` | Loops look up the tool name and call the executor |
| **Tools that call the model** | [agent/tools.py:139](1_agents_and_workflows/agent/tools.py:139) classify, [:184](1_agents_and_workflows/agent/tools.py:184) route, [:225](1_agents_and_workflows/agent/tools.py:225) draft | Nested model calls inside the module 1 live loop |
| **PostToolUse hook** | [hooks.py:34](1_agents_and_workflows/agent/hooks.py:34) `DraftFormattingHook`; [capstone hooks.py:31](capstone/agent/hooks.py:31) `ResponseFormattingHook`; [shared.py:107](1_agents_and_workflows/shared.py:107) `enforce_formatting` | Applied after each tool in the live loop and in `MockAgentLoop` (runner.py:147); capstone applies it at [orchestrator.py:413](capstone/agent/orchestrator.py:413); the workflow calls `enforce_formatting` directly |
| **Subagent (delegation)** | [subagent.py:120](1_agents_and_workflows/agent/subagent.py:120) specialist classifier; [capstone subagent.py:86](capstone/agent/subagent.py:86) `run_specialist` | Called when confidence < 0.7 or ambiguous (module 1); called when no tool matched ([orchestrator.py:399](capstone/agent/orchestrator.py:399)) |
| **Subagent for context isolation** | [6_.../subagent.py:211](6_prompt_and_context_engineering/subagent.py:211) `knowledge_base_lookup` returns `(full_result, compact_summary)` | `TechSupportAssistant.ask` keeps only the summary in context |
| **Agent framework (PydanticAI)** | [classifier.py](1_agents_and_workflows/pydantic_ai_component/classifier.py): `result_type` (:86), `@agent.tool`, `RunContext` | Module 1 `run_comparison.py` and the module's own `__main__` |

### A.2 Prompts, output and context

| Concept | Implemented in | Used / demonstrated by |
|---------|----------------|------------------------|
| **System prompt** | `AGENT_SYSTEM_PROMPT` in module 1 / module 4 runners ([broken](4_eval_testing_and_debugging/broken_app/runner.py:36), [fixed](4_eval_testing_and_debugging/fixed_app/runner.py:35)); [system_prompt.py:17](6_prompt_and_context_engineering/system_prompt.py:17); capstone `SYSTEM_PROMPT` | Sent as `system=` in every live call |
| **Few-shot examples** | module 6 `system_prompt.py`; specialist prompts in module 1 and the capstone | Steer format on vague / ambiguous inputs |
| **Instruction anchoring** | [system_prompt.py](6_prompt_and_context_engineering/system_prompt.py) (rules at start and end) | Checked by the 25-turn drift test in `run_session.py` |
| **Prompt versioning** | `prompts.system_v1/v2` and `active_version` in [config.yaml](2_applications_and_integration/config.yaml) | `get_system_prompt()` in module 2 |
| **Structured output + defensive parsing** | [structured_output.py:163](6_prompt_and_context_engineering/structured_output.py:163) `parse_response` (repair :86, fallback :61); [orchestrator.py:67](capstone/agent/orchestrator.py:67) `_parse_escalation_json` | `run_parser_test.py` (10 malformed inputs); every module 6 turn |
| **Heuristic answer structuring** | [claude_client.py:328](2_applications_and_integration/app/claude_client.py:328) `_parse_to_structured` (citations and confidence derived from the text) | `POST /sessions/{id}/ask` |
| **Pydantic models / enums** | [shared.py:60](1_agents_and_workflows/shared.py:60) `ClassificationResult` and siblings; [models.py:83](2_applications_and_integration/app/models.py:83) `StructuredAnswer` | Validation at every step boundary; FastAPI response models |
| **Context pruning and compaction** | [context_manager.py:50](6_prompt_and_context_engineering/context_manager.py:50) (`get_messages_for_api` :100, `_build_compacted_messages` :140, `_prune_tool_output` :173); [capstone manager.py:51](capstone/context/manager.py:51) | 25-turn session test; capstone regression eval (14 prior turns) |
| **Conversation summarization** | [session.py:121](2_applications_and_integration/app/session.py:121) `summarize_history` | Triggered after each turn when history passes the threshold |
| **Session lifecycle** | [session.py:159](2_applications_and_integration/app/session.py:159) `SessionManager`; capstone `SupportSession` and the `_sessions` dict in [app.py](capstone/app.py) | REST endpoints for create / get / reset / delete |

### A.3 Cost, models and performance

| Concept | Implemented in | Used / demonstrated by |
|---------|----------------|------------------------|
| **Prompt caching** | [claude_client.py:92](2_applications_and_integration/app/claude_client.py:92) `_build_system_prompt`; [summarizer.py:36](5_model_selection_and_optimization/task_c_summarization/summarizer.py:36) `summarize_live_cached` | Module 2 `usage` and `cached` flag; module 5 task C cached-vs-uncached comparison (:225) |
| **Cost formula (input/output/cache)** | [models.py:91](5_model_selection_and_optimization/models.py:91) `calculate_cost`; capstone `router.py` copy | Module 5 tracker; capstone cost tracker |
| **Token / latency / cost tracking** | [tracker.py:62](5_model_selection_and_optimization/tracker.py:62) `MetricsTracker` (`track` :77); [cost_tracker.py:44](capstone/models/cost_tracker.py:44) `CostTracker` | Module 5 runners; capstone step 8 in `process_message` |
| **Streaming** | [claude_client.py:155](2_applications_and_integration/app/claude_client.py:155) `ask_question_stream`, [:185](2_applications_and_integration/app/claude_client.py:185) `_stream_live` | SSE endpoint `.../ask/stream` ([routes.py:204](2_applications_and_integration/app/routes.py:204)) |
| **Extended thinking** | [reasoner.py:43](5_model_selection_and_optimization/task_b_reasoning/reasoner.py:43) `solve_extended_thinking_live` (`thinking=` at :48) | Module 5 task B (live helper only) |
| **Model selection / routing** | [router.py:128](capstone/models/router.py:128) `ModelRouter`, [:155](capstone/models/router.py:155) `classify_intent`; module 5 `models.py` registry | Capstone [orchestrator.py:362](capstone/agent/orchestrator.py:362); module 5 Haiku-vs-Sonnet task A |
| **Model pinning** | `model.name` in [config.yaml](2_applications_and_integration/config.yaml) via [config.py:45](2_applications_and_integration/app/config.py:45); `ModelId` enums in module 5 and capstone | Visible config diff on model changes; capstone Bug 1 guards the router's choice |

### A.4 Security

| Concept | Implemented in | Used / demonstrated by |
|---------|----------------|------------------------|
| **Input guardrail (Layer 1)** | [hooks.py:159](7_security_and_safety/hardened_app/hooks.py:159) `pre_process_hook`; [guardrails.py:192](capstone/security/guardrails.py:192) `pre_process_check` | Module 7 attack runs; capstone step 1 ([orchestrator.py:338](capstone/agent/orchestrator.py:338)); EVAL-008/009 |
| **Input isolation (Layer 2)** | [summarizer.py:58](7_security_and_safety/hardened_app/summarizer.py:58) `_build_prompt` + `SYSTEM_PROMPT` | Module 7 hardened app; checked structurally in `layer_checks.py` |
| **Output content policy (Layer 3)** | [content_policy.py:93](7_security_and_safety/hardened_app/content_policy.py:93) `check_content_policy`; [guardrails.py:229](capstone/security/guardrails.py:229) `post_process_check` | Module 7 hardened pipeline; capstone step 6 ([orchestrator.py:418](capstone/agent/orchestrator.py:418)); `layer_checks.py` |
| **Identity / permission checks (Layer 4)** | [actions.py:37](7_security_and_safety/hardened_app/actions.py:37) `_AUTHORIZED_USERS`; `send_email` (:96), `delete_user_data` (:146) | `layer_checks.py` (no token / analyst / admin) |
| **Audit logging** | [actions.py:70](7_security_and_safety/hardened_app/actions.py:70) `_audit` (records token presence, never the token) | `layer_checks.py` verifies no token text is logged |
| **Secrets handling and audit** | `os.environ` loading and key masking in `hardened_app/actions.py`; [secrets_audit.py](7_security_and_safety/secrets_audit.py); [capstone secrets_audit.py](capstone/security/secrets_audit.py); `.env.example`, `.gitignore`; deny rules in module 3 `settings.json` | Module 7 comparison; capstone secrets audit |
| **Deliberately vulnerable target** | `7_.../vulnerable_app/` (no isolation, no-op [hooks](7_security_and_safety/vulnerable_app/hooks.py:15), hardcoded fake secrets) | `run_vulnerable.py` (10/10 exploited) |

### A.5 Evaluation and debugging

| Concept | Implemented in | Used / demonstrated by |
|---------|----------------|------------------------|
| **Ground-truth test data** | `ground_truth` on each ticket in `tickets.py`; `EvalCase`s at [eval_suite.py:113](capstone/eval/eval_suite.py:113) | Tracer checks; capstone eval runner |
| **Tracing and anomaly detection** | [tracer.py:52](4_eval_testing_and_debugging/tracer.py:52) `analyze_ticket_trace` | `run_broken.py`, `run_fixed.py`, `run_comparison.py` |
| **Integration bug vs model-output bug** | Bug 1 at [broken_app/tools.py:189](4_eval_testing_and_debugging/broken_app/tools.py:189); Bug 2 in the broken vs fixed `AGENT_SYSTEM_PROMPT` | `diagnosis/hypothesis.md`, `diagnosis/trace_analysis.md` |
| **Simulated model driven by the prompt** | [mock_model.py:42](4_eval_testing_and_debugging/mock_model.py:42) and `rubric_priority` | `MockAgentLoop._judge_priority` in both apps |
| **Eval suite runner** | [run_evals.py:90](capstone/eval/run_evals.py:90) `run_all_evals` | `/run-evals` command; `capstone/eval/run_evals.py` |
| **Seeded bugs and their detection** | [seeded_bugs.py:125](capstone/eval/seeded_bugs.py:125) `verify_bug_1_is_fixed`, [:149](capstone/eval/seeded_bugs.py:149) `verify_bug_2_is_fixed` | Run after the eval cases; Bug 2 reported as `DETECTED (expected)` |
| **Per-layer defense testing** | [layer_checks.py:81](7_security_and_safety/layer_checks.py:81) `run_layer_checks` | Called from module 7 `run_comparison.py` |

### A.6 Tools, protocols and Claude Code

| Concept | Implemented in | Used / demonstrated by |
|---------|----------------|------------------------|
| **MCP tools / resource / prompt** | [server.py](8_tools_and_MCPs/mcp_server/server.py): tools (:79, :100, :117), resource (:132), prompt (:151); [capstone mcp_server.py:62](capstone/data/mcp_server.py:62) | Module 8 client; the capstone server is standalone (not called by the orchestrator) |
| **MCP client over stdio** | [client.py:81](8_tools_and_MCPs/mcp_server/client.py:81) `stdio_client`, `ClientSession` | Module 8 `mcp_server/runner.py` and `run_all.py` equivalence check |
| **Skill** | [SKILL.md](8_tools_and_MCPs/skill/SKILL.md) + [inventory_skill.py](8_tools_and_MCPs/skill/scripts/inventory_skill.py) | Module 8 `skill/runner.py` (subprocess) |
| **Structured error model** | [error_model.py:20](8_tools_and_MCPs/error_model.py:20) `make_error` and helpers | Shared by the custom tool, the Skill and the MCP server |
| **CLAUDE.md hierarchy** | [3_claude_code/CLAUDE.md](3_claude_code/CLAUDE.md), [sample_subfolder/CLAUDE.md](3_claude_code/sample_subfolder/CLAUDE.md), [capstone/CLAUDE.md](capstone/CLAUDE.md) | `verify_memory.md`; `validate_setup.py` |
| **Permissions (allow/deny)** | [.claude/settings.json](3_claude_code/.claude/settings.json) | `validate_setup.py` permission check |
| **Custom slash commands** | [summarize-changes.md](3_claude_code/.claude/commands/summarize-changes.md); [run-evals.md](capstone/.claude/commands/run-evals.md) | Invoked as `/summarize-changes` and `/run-evals` |
| **Headless mode (`claude -p`)** | [headless_summary.py](3_claude_code/scripts/headless_summary.py), `headless_summary.ps1` | `validate_setup.py --headless` |

### A.7 Application, infrastructure and patterns

| Concept | Implemented in | Used / demonstrated by |
|---------|----------------|------------------------|
| **REST API design** | [routes.py](2_applications_and_integration/app/routes.py), [main.py](2_applications_and_integration/app/main.py); [capstone app.py](capstone/app.py) | Swagger UI at `/docs`; `run_validation.py` route check |
| **Mock mode + client bootstrap** | `_get_client` at [runner.py:257](1_agents_and_workflows/agent/runner.py:257), [claude_client.py:44](2_applications_and_integration/app/claude_client.py:44), [orchestrator.py:151](capstone/agent/orchestrator.py:151) | Every module; `main.py` runs all of them without a key |
| **Orchestrating all modules** | [main.py:23](main.py:23) `MODULES`, [:106](main.py:106) `main` | Writes `output/run_report.md`; exit code reflects failures |
| **Batches API decision (no code)** | Written justification in the module 2 README | Design rationale only |
| **Code review practice** | [code_review.md](2_applications_and_integration/code_review.md) | Issue 1 addressed; issues 2–4 recorded for production |
| **Deterministic vs probabilistic control** | Hooks (module 1, capstone), regex guardrails and permission checks (module 7, capstone) vs prompt rules | Compared in module 1, 7 and capstone READMEs |

---

*Run everything:* `uv run python main.py` (modules 1–8), then
`uv run python capstone/run_capstone.py`, `uv run python capstone/eval/run_evals.py`, and
`uv run pytest 2_applications_and_integration/tests`.
