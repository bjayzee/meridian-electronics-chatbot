from __future__ import annotations

import json
import logging
from typing import Any

from mcp import ClientSession
from openai import AsyncOpenAI

from meridian_support.config import Settings
from meridian_support.mcp_bridge import call_mcp_tool, list_mcp_tools_openai_format

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are Meridian Electronics' helpful customer support assistant. Meridian sells monitors, keyboards, printers, networking equipment, and accessories.

Behavior:
- Use the provided tools for inventory, customers, and orders. Never invent SKUs, prices, or order IDs.
- For order history or placing orders, the customer must be identified. Use verify_customer_pin with their email and 4-digit PIN when they want account-specific help. Do not repeat their PIN in your replies.
- After successful verification, you may use list_orders, get_order, or create_order with the customer_id returned by the tool output.
- To check stock or browse products, use search_products, list_products, or get_product.
- If a tool returns an error, explain it clearly and suggest next steps (e.g., double-check email/PIN, SKU).
- Keep replies concise and professional. Offer to escalate only if the request cannot be satisfied with available tools.

Company: Meridian Electronics."""


async def run_agent_turn(
    *,
    settings: Settings,
    openai_client: AsyncOpenAI,
    mcp_session: ClientSession,
    messages: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], str]:
    """
    Run one user/assistant turn: may execute multiple MCP tool rounds.

    Returns:
        (updated_messages, assistant_visible_reply) — updated_messages includes new assistant + tool messages.
    """
    tools = await list_mcp_tools_openai_format(mcp_session)
    working = _ensure_system_message(list(messages))

    final_assistant_text = ""

    for _ in range(settings.agent_max_rounds):
        completion = await openai_client.chat.completions.create(
            model=settings.openai_model,
            messages=working,
            tools=tools,
            tool_choice="auto",
            temperature=0.2,
        )
        msg = completion.choices[0].message

        assistant_record: dict[str, Any] = {
            "role": "assistant",
            "content": msg.content,
        }
        if msg.tool_calls:
            assistant_record["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments or "{}",
                    },
                }
                for tc in msg.tool_calls
            ]
        working.append(assistant_record)

        if not msg.tool_calls:
            final_assistant_text = (msg.content or "").strip()
            break

        for tc in msg.tool_calls:
            name = tc.function.name
            try:
                raw_args = tc.function.arguments or "{}"
                args = json.loads(raw_args) if isinstance(raw_args, str) else {}
                if not isinstance(args, dict):
                    args = {}
            except json.JSONDecodeError:
                args = {}
                logger.warning("Invalid JSON arguments from model for %s", name)

            try:
                tool_text = await call_mcp_tool(mcp_session, name, args)
            except Exception as exc:  # noqa: BLE001 — surface as tool output for recovery
                logger.exception("MCP tool failure name=%s", name)
                tool_text = f"[tool execution error: {exc}]"

            working.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": tool_text,
                }
            )
    else:
        final_assistant_text = (
            "I could not finish all steps within the allowed number of tool rounds. "
            "Please try a simpler question or contact support."
        )
        working.append({"role": "assistant", "content": final_assistant_text})

    if not final_assistant_text:
        final_assistant_text = "I'm sorry, something went wrong. Please try again."

    return working, final_assistant_text


def _ensure_system_message(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = list(messages)
    if not out or out[0].get("role") != "system":
        out.insert(0, {"role": "system", "content": SYSTEM_PROMPT})
    else:
        # Keep caller system first line but ensure our policy is present if minimal
        first = out[0].get("content") or ""
        if "Meridian Electronics" not in first:
            out[0] = {
                "role": "system",
                "content": SYSTEM_PROMPT + "\n\n" + first,
            }
    return out


def trim_messages_for_storage(
    messages: list[dict[str, Any]],
    max_messages: int = 40,
) -> list[dict[str, Any]]:
    """Keep system + recent turns to bound token usage."""
    if len(messages) <= max_messages:
        return messages
    system = [m for m in messages if m.get("role") == "system"]
    rest = [m for m in messages if m.get("role") != "system"]
    keep = rest[-(max_messages - len(system)) :]
    return system + keep
