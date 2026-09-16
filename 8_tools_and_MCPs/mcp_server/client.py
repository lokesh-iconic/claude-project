"""
client.py — MCP client that connects to the inventory server via stdio.

Programmatically calls each tool, reads the resource, and uses the prompt.
This demonstrates how an MCP client would interact with the server.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from error_model import is_error

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    HAS_MCP = True
except ImportError:
    HAS_MCP = False

SERVER_SCRIPT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "server.py",
)


async def call_tool(session: "ClientSession", tool_name: str, arguments: dict) -> dict:
    """Call an MCP tool and return the parsed result."""
    result = await session.call_tool(tool_name, arguments=arguments)

    # Extract text content from the result
    if result.content:
        for block in result.content:
            if hasattr(block, "text"):
                return json.loads(block.text)

    return {"error": {"category": "internal_error", "retryable": True,
                      "description": "No text content in MCP tool response"}}


async def read_resource(session: "ClientSession", uri: str) -> dict:
    """Read an MCP resource and return parsed content."""
    result = await session.read_resource(uri)

    if result.contents:
        for block in result.contents:
            if hasattr(block, "text"):
                return json.loads(block.text)

    return {"error": {"category": "internal_error", "retryable": True,
                      "description": "No content in MCP resource response"}}


async def get_prompt(session: "ClientSession", prompt_name: str, arguments: dict) -> str:
    """Get a rendered MCP prompt."""
    result = await session.get_prompt(prompt_name, arguments=arguments)

    if result.messages:
        for msg in result.messages:
            if hasattr(msg.content, "text"):
                return msg.content.text

    return ""


async def run_mcp_queries() -> list[dict]:
    """Connect to the MCP server, run all 5 test queries, and return results."""
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[SERVER_SCRIPT],
        env={**os.environ},
    )

    results = []

    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            # List available tools
            tools_response = await session.list_tools()
            tool_names = [t.name for t in tools_response.tools]

            # List resources
            resources_response = await session.list_resources()
            resource_uris = [r.uri for r in resources_response.resources]

            # List prompts
            prompts_response = await session.list_prompts()
            prompt_names = [p.name for p in prompts_response.prompts]

            info = {
                "tools": tool_names,
                "resources": [str(u) for u in resource_uris],
                "prompts": prompt_names,
            }

            # Test queries (same 5 as custom_tool and skill)
            test_queries = [
                ("SKU lookup (exists)",    "inventory_lookup",    {"sku": "SKU-003"}),
                ("SKU lookup (not found)", "inventory_lookup",    {"sku": "SKU-999"}),
                ("Name search",            "inventory_search",    {"query": "desk"}),
                ("Low stock report",       "inventory_low_stock", {}),
                ("Search (no results)",    "inventory_search",    {"query": "xyz-nonexistent"}),
            ]

            for label, tool_name, tool_input in test_queries:
                result = await call_tool(session, tool_name, tool_input)
                results.append({
                    "label": label,
                    "tool_name": tool_name,
                    "tool_input": tool_input,
                    "result": result,
                })

            # Also read the resource (bonus — MCP can do this, others can't)
            catalog = await read_resource(session, "inventory://catalog")
            results.append({
                "label": "Resource: Full catalog",
                "tool_name": "resource:inventory://catalog",
                "tool_input": {},
                "result": {"total_products": catalog.get("total_products", 0)},
            })

            # Also get a prompt (bonus — MCP can do this, others can't)
            prompt_text = await get_prompt(
                session, "inventory_check",
                {"question": "What products are running low?"},
            )
            results.append({
                "label": "Prompt: inventory_check",
                "tool_name": "prompt:inventory_check",
                "tool_input": {"question": "What products are running low?"},
                "result": {"prompt_text": prompt_text[:100] + "..." if prompt_text else ""},
            })

    return results, info


if __name__ == "__main__":
    if not HAS_MCP:
        print("MCP SDK not installed. Run: uv add mcp")
        sys.exit(1)

    results, info = asyncio.run(run_mcp_queries())
    print(json.dumps(results, indent=2))
