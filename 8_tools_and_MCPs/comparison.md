# Comparison: Custom Tool vs. Skill vs. MCP Server

## The Capability

**Internal inventory lookup** — query a product database by SKU, search by name, or list low-stock items. All three implementations use the same underlying data and error model.

## Side-by-Side

| Dimension | Custom Tool | Skill | MCP Server |
|-----------|------------|-------|------------|
| **What it is** | JSON Schema tool definition + Python executor function | Markdown instruction file (SKILL.md) + standalone CLI script | FastMCP server process exposing tools, resources, and prompts over stdio |
| **Interface** | Anthropic API `tool_use` content blocks | `subprocess` invocation with CLI args | JSON-RPC over stdio (MCP protocol) |
| **Error format** | Structured dict: `{error: {category, retryable, description}}` | Same structured dict (JSON to stdout) | Same structured dict (JSON in tool response) |
| **Schema** | Explicit JSON Schema in `tool_definitions.py` | Documented in SKILL.md; implicit in CLI args | Auto-generated from Python type hints by FastMCP |
| **Process model** | In-process (same Python runtime as the agent) | Out-of-process (subprocess per invocation) | Out-of-process (persistent subprocess) |
| **Extra capabilities** | — | — | Resources (read-only data), Prompts (templates) |

## Which is reusable across applications?

| Implementation | Reusable? | How |
|----------------|-----------|-----|
| **Custom Tool** | ❌ Not easily | The tool schema + executor are Python code embedded in your application. Another team would need to copy the files and wire them into their own agent loop. |
| **Skill** | ✅ Yes (within Claude Code) | Another team references the SKILL.md path and Claude Code loads it automatically. The CLI script is invoked without code changes. But it only works within the Claude Code ecosystem. |
| **MCP Server** | ✅ Yes (universally) | Any MCP-compatible client — Claude Desktop, Claude Code, VS Code, or a custom app — can connect to the server. No code copying. Language-agnostic: a TypeScript client can call a Python MCP server. |

**Answer to self-check #1:** The MCP server is the most reusable — any MCP-compatible client can use it without copying code. The Skill is reusable within Claude Code. The custom tool requires code copying.

## Which is fastest to build?

| Implementation | Time | Why |
|----------------|------|-----|
| **Custom Tool** | ⚡ Fastest | Just write Python functions and a JSON schema dict. No packaging, no extra dependencies, no transport layer. |
| **Skill** | 🔧 Medium | Need to write the script, the SKILL.md with proper frontmatter, and ensure JSON output. Packaging overhead is small but non-zero. |
| **MCP Server** | 🏗️ Slowest | Need the MCP SDK dependency, understanding of the MCP protocol, and handling of async I/O, transport, and lifecycle. FastMCP greatly simplifies this, but there's still more setup than a plain function. |

## Which would you choose in production — and why?

**It depends on the use case:**

| Scenario | Best Choice | Reasoning |
|----------|-------------|-----------|
| Single application, one team | **Custom Tool** | Simplest. No dependencies beyond Anthropic SDK. Direct function calls are fastest at runtime. Structured errors are built into the tool executor. |
| Claude Code workflow, shared across team | **Skill** | The team references the same SKILL.md. No server to run. Scripts update independently of the consuming agent. Good for internal tooling. |
| Multi-application, cross-team, or cross-language | **MCP Server** | The server runs independently. Any MCP client connects to it. Updates to the server don't require changes in consumers. Resources and prompts give richer context. This is the right choice when the capability needs to be a shared service. |

**Answer to self-check #3:** For this specific capability (internal inventory lookup used by one team), I'd choose a **Custom Tool** — it's the fastest to build, has no extra dependencies, and the structured error handling is identical. I'd switch to MCP only if a second team or a non-Python client needed access.

## Structured Error Handling

All three implementations return errors in the same format:

```json
{
    "error": {
        "category": "not_found",
        "retryable": false,
        "description": "No product found with SKU 'SKU-999'"
    }
}
```

**Answer to self-check #2:** Yes — the MCP server's error handling follows the exact same structured-error pattern (category, retryable, description) as the custom tool. They share the `error_model.py` module, so the format is guaranteed identical.
