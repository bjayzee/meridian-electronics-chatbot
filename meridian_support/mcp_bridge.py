from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.types import CallToolResult, TextContent

logger = logging.getLogger(__name__)

SENSITIVE_TOOL_NAMES = frozenset({"verify_customer_pin"})


def _redact_tool_args(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name not in SENSITIVE_TOOL_NAMES:
        return arguments
    redacted = dict(arguments)
    if "pin" in redacted:
        redacted["pin"] = "**redacted**"
    return redacted


def call_tool_result_to_text(result: CallToolResult) -> str:
    chunks: list[str] = []
    for block in result.content or []:
        if isinstance(block, TextContent):
            chunks.append(block.text)
        else:
            chunks.append(str(block))
    text = "\n".join(chunks).strip()
    if result.isError:
        return f"[tool error]\n{text}" if text else "[tool error] Unknown failure."
    return text if text else "(empty result)"

# Convert an MCP Tool to OpenAI Chat Completions tool schema.
def mcp_tool_to_openai_function(tool) -> dict[str, Any]:
    
    schema = tool.inputSchema
    if not isinstance(schema, dict):
        schema = {"type": "object", "properties": {}}
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": (tool.description or "").strip() or f"MCP tool `{tool.name}`.",
            "parameters": schema,
        },
    }


# Open MCP Streamable HTTP session, initialize, yield ClientSession, then close.
@asynccontextmanager
async def mcp_client_session(mcp_url: str) -> AsyncIterator[ClientSession]:
    url = mcp_url.rstrip("/")
    async with streamable_http_client(url) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            yield session


async def call_mcp_tool(
    session: ClientSession,
    name: str,
    arguments: dict[str, Any] | None,
) -> str:
    """Execute a tool on the MCP session and return text for the model."""
    args = arguments or {}
    safe_log = _redact_tool_args(name, args)
    logger.info("MCP call_tool name=%s arguments=%s", name, json.dumps(safe_log))
    result = await session.call_tool(name, args)
    return call_tool_result_to_text(result)


async def list_mcp_tools_openai_format(session: ClientSession) -> list[dict[str, Any]]:
    """List tools from MCP and convert to OpenAI tool definitions."""
    listed = await session.list_tools()
    return [mcp_tool_to_openai_function(t) for t in listed.tools]
