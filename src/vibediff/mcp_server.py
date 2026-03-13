"""VibeDiff MCP tool server — expose review and learn as MCP tools."""

from __future__ import annotations

import json

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import TextContent, Tool
    HAS_MCP = True
except ImportError:
    HAS_MCP = False

from vibediff.cli import run_learn, run_review

REVIEW_DESC = (
    "Review a diff for AI patterns, style drift, "
    "collaboration quality, and idiom contamination."
)

REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "target": {
            "type": "string", "default": "HEAD~1",
            "description": "Git ref or PR number.",
        },
        "pr": {
            "type": "boolean", "default": False,
            "description": "Treat target as a GitHub PR.",
        },
        "no_fingerprint": {
            "type": "boolean", "default": False,
            "description": "Skip style drift analysis.",
        },
        "synthesize": {
            "type": "boolean", "default": False,
            "description": "LLM synthesis (needs API key).",
        },
    },
}

LEARN_SCHEMA = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string", "default": ".",
            "description": "Path to scan.",
        },
        "force": {
            "type": "boolean", "default": False,
            "description": "Overwrite existing fingerprint.",
        },
    },
}


def _make_server():
    if not HAS_MCP:
        raise ImportError(
            "MCP server requires 'mcp': pip install vibediff[mcp]"
        )
    server = Server("vibediff")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="review",
                description=REVIEW_DESC,
                inputSchema=REVIEW_SCHEMA,
            ),
            Tool(
                name="learn",
                description="Learn codebase conventions.",
                inputSchema=LEARN_SCHEMA,
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        if name == "review":
            result = run_review(
                target=arguments.get("target", "HEAD~1"),
                pr=arguments.get("pr", False),
                no_fingerprint=arguments.get("no_fingerprint", False),
                do_synth=arguments.get("synthesize", False),
            )
            if result is None:
                text = "No changes found."
            else:
                text = json.dumps(result, indent=2)
            return [TextContent(type="text", text=text)]

        if name == "learn":
            result = run_learn(
                path=arguments.get("path", "."),
                force=arguments.get("force", False),
            )
            if result is None:
                text = "Fingerprint exists. Use force=true to rebuild."
            else:
                text = json.dumps(result, indent=2)
            return [TextContent(type="text", text=text)]

        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    return server


async def _run_async():
    server = _make_server()
    async with stdio_server() as (read, write):
        await server.run(
            read, write, server.create_initialization_options()
        )


def run_server():
    """Entry point for the MCP server."""
    if not HAS_MCP:
        print(
            "MCP server requires 'mcp': pip install vibediff[mcp]"
        )
        return
    import asyncio
    asyncio.run(_run_async())
