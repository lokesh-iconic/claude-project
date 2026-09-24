"""
mcp_server.py — MCP server exposing the knowledge base for the support assistant.

WHY MCP AND NOT A CUSTOM TOOL?
===============================
The knowledge base is a READ-ONLY reference data source — it doesn't change
per-request and doesn't need tight integration with the agent loop. MCP's
resource model (inventory://catalog pattern) is ideal:
  - Decoupled: other agents/tools can also access the KB without code changes
  - Resource-based: the full article catalog is available as a browsable resource
  - Tool-based: search is exposed as a callable tool for targeted queries

Compare to the order lookup custom tool, which is tightly coupled to the
agent loop (per-request, user-specific data, structured error handling).

Uses FastMCP (same pattern as Domain 8's inventory MCP server).
"""

from __future__ import annotations

import json
import os
import sys

# Ensure parent packages are importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from knowledge_base import (
    search_articles,
    get_article_by_id,
    list_articles_by_category,
    get_all_articles,
    ARTICLES,
)

try:
    from mcp.server.fastmcp import FastMCP
    HAS_MCP = True
except ImportError:
    try:
        from fastmcp import FastMCP
        HAS_MCP = True
    except ImportError:
        HAS_MCP = False


if not HAS_MCP:
    print(
        json.dumps({
            "error": "MCP SDK not installed. Run: uv add mcp",
            "hint": "pip install mcp  OR  pip install fastmcp",
        }),
        file=sys.stderr,
    )
    sys.exit(1)


# ---------------------------------------------------------------------------
# Initialize the MCP server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    name="Knowledge Base Server",
    instructions=(
        "This server provides access to the product knowledge base and FAQ system. "
        "Use the tools to search articles by keyword or browse by category. "
        "The kb://catalog resource provides the full article catalog."
    ),
)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def kb_search(query: str) -> str:
    """Search knowledge base articles by keyword.

    Use when the customer has a question about shipping, returns, billing,
    products, or account management. Returns matching FAQ articles.

    Args:
        query: Search term (e.g. 'shipping times', 'return policy', 'warranty').
    """
    if not query or not query.strip():
        return json.dumps({"error": "Parameter 'query' is required"})

    results = search_articles(query.strip())
    return json.dumps({"articles": results, "count": len(results)})


@mcp.tool()
def kb_get_article(article_id: str) -> str:
    """Get a specific knowledge base article by its ID.

    Args:
        article_id: The article ID (e.g. 'KB-001').
    """
    if not article_id or not article_id.strip():
        return json.dumps({"error": "Parameter 'article_id' is required"})

    result = get_article_by_id(article_id.strip())
    if result is None:
        return json.dumps({"error": f"Article '{article_id}' not found"})
    return json.dumps({"article": result})


@mcp.tool()
def kb_list_category(category: str) -> str:
    """List all knowledge base articles in a category.

    Args:
        category: One of: shipping, returns, billing, product, account.
    """
    if not category or not category.strip():
        return json.dumps({"error": "Parameter 'category' is required"})

    results = list_articles_by_category(category.strip())
    return json.dumps({"articles": results, "count": len(results)})


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------

@mcp.resource("kb://catalog")
def get_catalog() -> str:
    """Full knowledge base catalog — all articles with content and tags.

    This read-only resource provides the entire FAQ system as a JSON document.
    """
    articles = get_all_articles()
    categories = {}
    for article in articles:
        cat = article["category"]
        if cat not in categories:
            categories[cat] = 0
        categories[cat] += 1

    return json.dumps({
        "articles": articles,
        "total_articles": len(articles),
        "categories": categories,
    }, indent=2)


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

@mcp.prompt()
def support_question(question: str) -> str:
    """Pre-built prompt template for customer support questions.

    Args:
        question: The customer's support question.
    """
    return (
        f"You are a customer support assistant. Use the kb_search, kb_get_article, "
        f"and kb_list_category tools to answer the following customer question.\n\n"
        f"Question: {question}\n\n"
        f"Provide a clear, helpful answer based on the knowledge base articles. "
        f"If the information is not in the knowledge base, say so and suggest "
        f"contacting support directly."
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run(transport="stdio")
