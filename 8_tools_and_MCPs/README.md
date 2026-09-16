# Tools and MCPs — Build the Same Capability Three Ways

Implement one genuine capability three different ways — as a custom tool, as a Skill, and as an MCP server — so you can articulate the real tradeoffs instead of defaulting to whichever you're most comfortable with.

## Problem Statement

When you need to expose a capability to an AI agent, there are multiple approaches: custom tool definitions, Skills, and MCP servers. Each has different reusability, setup cost, and runtime characteristics. This module implements the same **internal inventory lookup** three ways, tests all three from the same runner, and provides a data-backed comparison.

## Project Structure

```
8_tools_and_MCPs/
├── README.md                           ← You are here
├── __init__.py
├── inventory_data.py                   ← Shared product database (15 products, 3 categories)
├── error_model.py                      ← Structured error format (shared by all three)
│
├── custom_tool/                        ← Implementation 1: Anthropic tool_use
│   ├── __init__.py
│   ├── tool_definitions.py             ← JSON Schema tool definitions
│   ├── tool_executor.py                ← Tool executor + mock agent loop
│   └── runner.py                       ← Test runner
│
├── skill/                              ← Implementation 2: Claude Code Skill
│   ├── SKILL.md                        ← Skill definition with frontmatter
│   ├── scripts/
│   │   └── inventory_skill.py          ← Standalone CLI script
│   └── runner.py                       ← Test runner (subprocess invocation)
│
├── mcp_server/                         ← Implementation 3: MCP Server
│   ├── __init__.py
│   ├── server.py                       ← MCPServer with tools + resource + prompt
│   ├── client.py                       ← MCP client (stdio connection)
│   └── runner.py                       ← Test runner
│
├── comparison.md                       ← Written tradeoff analysis
├── run_all.py                          ← Run all three + equivalence check
└── output/
    └── comparison_report.md            ← Generated comparison report
```

## Running

```bash
# Run all three implementations + equivalence check (recommended)
uv run python .\8_tools_and_MCPs\run_all.py

# Run individually
uv run python .\8_tools_and_MCPs\custom_tool\runner.py
uv run python .\8_tools_and_MCPs\skill\runner.py
uv run python .\8_tools_and_MCPs\mcp_server\runner.py
```

## How It Works

### The Capability: Internal Inventory Lookup

A product database with 15 items across 3 categories (electronics, office supplies, furniture). Each product has: SKU, name, category, price, stock level, warehouse, reorder point.

Three operations:
- **`inventory_lookup(sku)`** — Look up a single product by SKU
- **`inventory_search(query)`** — Search products by name (substring match)
- **`inventory_low_stock()`** — List products at or below their reorder point

All three implementations share [`inventory_data.py`](inventory_data.py) and [`error_model.py`](error_model.py), so results are guaranteed identical.

### Implementation 1: Custom Tool ([`custom_tool/`](custom_tool/))

| Component | What It Does |
|-----------|-------------|
| [`tool_definitions.py`](custom_tool/tool_definitions.py) | JSON Schema definitions for 3 tools (Anthropic `tool_use` format) with clear, differentiated descriptions |
| [`tool_executor.py`](custom_tool/tool_executor.py) | Executes tool calls by name, validates inputs, returns structured results or structured errors |

The tool definitions include:
- **Differentiated descriptions** — each tool explains *when* to use it, not just what it does
- **Typed input schemas** — required parameters with descriptions
- **Structured errors** — `{category, retryable, description}` for every failure mode

### Implementation 2: Skill ([`skill/`](skill/))

| Component | What It Does |
|-----------|-------------|
| [`SKILL.md`](skill/SKILL.md) | Proper YAML frontmatter (`name`, `description`), usage instructions, output format docs |
| [`scripts/inventory_skill.py`](skill/scripts/inventory_skill.py) | Standalone CLI: `python inventory_skill.py lookup SKU-001` → JSON to stdout |

The skill is invoked via `subprocess`, producing structured JSON:
```bash
python inventory_skill.py lookup SKU-001   # → {"product": {...}}
python inventory_skill.py search "desk"    # → {"products": [...], "count": 2}
python inventory_skill.py low-stock        # → {"products": [...], "count": 5}
```

### Implementation 3: MCP Server ([`mcp_server/`](mcp_server/))

| Component | What It Does |
|-----------|-------------|
| [`server.py`](mcp_server/server.py) | MCPServer (MCP v2) exposing 3 tools + 1 resource + 1 prompt over stdio |
| [`client.py`](mcp_server/client.py) | MCP client that connects via stdio, calls tools, reads resources |

The MCP server exposes three types of capabilities:

| Type | Name | Purpose |
|------|------|---------|
| **Tool** | `inventory_lookup`, `inventory_search`, `inventory_low_stock` | Same operations as custom tool and skill |
| **Resource** | `inventory://catalog` | Full product catalog as read-only data (MCP-exclusive) |
| **Prompt** | `inventory_check` | Pre-built prompt template for inventory queries (MCP-exclusive) |

### Structured Error Handling (Shared)

All three implementations return errors in the same format ([`error_model.py`](error_model.py)):

```json
{
    "error": {
        "category": "not_found",
        "retryable": false,
        "description": "No product found with SKU 'SKU-999'"
    }
}
```

| Category | Retryable | When |
|----------|-----------|------|
| `not_found` | No | SKU doesn't exist |
| `invalid_input` | No | Missing or empty required parameter |
| `internal_error` | Yes | Unexpected failure |

## Results

### Equivalence Check

All three implementations produce identical results for the same 5 queries:

| # | Query | Custom Tool | Skill | MCP | Match |
|---|-------|------------|-------|-----|-------|
| 1 | SKU lookup (exists) | 1 product | 1 product | 1 product | ✓ |
| 2 | SKU lookup (not found) | err:not_found | err:not_found | err:not_found | ✓ |
| 3 | Name search | 2 products | 2 products | 2 products | ✓ |
| 4 | Low stock report | 5 products | 5 products | 5 products | ✓ |
| 5 | Search (no results) | 0 products | 0 products | 0 products | ✓ |

### Feature Comparison

| Feature | Custom Tool | Skill | MCP Server |
|---------|------------|-------|------------|
| Tool invocation | ✓ | ✓ | ✓ |
| Structured errors | ✓ | ✓ | ✓ |
| Read-only data resources | — | — | ✓ |
| Prompt templates | — | — | ✓ |
| Cross-application reuse | — | ✓ | ✓ |
| No code copying needed | — | ✓ | ✓ |
| Works without SDK dependency | ✓ | ✓ | — |
| Process isolation | — | ✓ | ✓ |
| Language-agnostic interface | — | — | ✓ |
| Discoverable (list_tools) | — | — | ✓ |

Full tradeoff analysis: [`comparison.md`](comparison.md)

## Self-Check

| Question | Answer |
|----------|--------|
| If another team wanted to reuse this capability in a different application, which of your three implementations could they actually reuse without copying code? | **MCP Server** — any MCP-compatible client connects to it without copying code or adding Python to their stack. **Skill** — reusable within Claude Code by referencing the SKILL.md path. **Custom Tool** — requires copying Python files into the new application. |
| Does your MCP server's error handling follow the same structured-error pattern (category, retryable, description) as a well-designed custom tool? | **Yes** — all three implementations share `error_model.py`. The MCP server returns `{"error": {"category": "not_found", "retryable": false, "description": "..."}}` — identical to the custom tool and skill. |
| Could you defend your final choice to a technical reviewer in two sentences? | **For a single-team internal lookup, use a Custom Tool** — it's the fastest to build, has no extra dependencies, and the structured error handling is identical. **Switch to MCP only when a second team, a non-Python client, or a different application needs access** — that's when the server's process isolation and protocol standardization justify the setup cost. |

## Mock vs. Live Mode

All scripts run in **mock mode** by default (no API key needed):
- The custom tool's mock agent loop uses keyword matching for tool selection
- The skill script and MCP server operate on the shared database directly
- Results are deterministic and identical across runs

This module focuses on the three different *interfaces* (JSON schema, CLI script, MCP protocol) wrapping the same underlying capability. The tool definitions, schemas, and error patterns work identically in both modes.

To run the custom tool runner in **live mode** (where the Anthropic API selects which tool to call instead of keyword matching):

1. Ensure `ANTHROPIC_API_KEY` is set in the `.env` file at the project root (or as an environment variable)
2. Optionally set `CLAUDE_MODEL` to override the default model (defaults to `claude-sonnet-4-20250514`)
3. Add the `--live` flag:

```bash
uv run python .\8_tools_and_MCPs\custom_tool\runner.py --live
uv run python .\8_tools_and_MCPs\run_all.py --live
```

The skill and MCP server runners don't require an API key — they execute the inventory operations directly. The MCP server requires the `mcp` SDK (`uv add mcp`), which is already installed as a project dependency.
