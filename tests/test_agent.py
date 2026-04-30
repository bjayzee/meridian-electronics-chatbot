import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from meridian_support.agent import run_agent_turn, trim_messages_for_storage
from meridian_support.config import Settings


@pytest.mark.asyncio
async def test_run_agent_turn_no_tools() -> None:
    settings = Settings(
        openai_api_key="test",
        openai_model="gpt-4o-mini",
        mcp_server_url="https://example.invalid/mcp",
    )
    client = AsyncMock()
    client.chat.completions.create = AsyncMock(
        return_value=MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content="Hello from Meridian.",
                        tool_calls=None,
                    )
                )
            ]
        )
    )
    mcp = AsyncMock()
    mcp_session = mcp  # unused — no tool calls

    updated, reply = await run_agent_turn(
        settings=settings,
        openai_client=client,
        mcp_session=mcp_session,
        messages=[{"role": "user", "content": "Hi"}],
    )
    assert reply == "Hello from Meridian."
    assert any(m.get("role") == "assistant" for m in updated)


@pytest.mark.asyncio
async def test_run_agent_turn_with_tool_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        openai_api_key="test",
        openai_model="gpt-4o-mini",
        mcp_server_url="https://example.invalid/mcp",
        agent_max_rounds=5,
    )

    call_sequence = [
        MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content=None,
                        tool_calls=[
                            MagicMock(
                                id="call_1",
                                function=MagicMock(
                                    name="search_products",
                                    arguments=json.dumps({"query": "monitor"}),
                                ),
                            )
                        ],
                    )
                )
            ]
        ),
        MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content="Here are monitors.",
                        tool_calls=None,
                    )
                )
            ]
        ),
    ]

    client = AsyncMock()
    client.chat.completions.create = AsyncMock(side_effect=call_sequence)

    async def fake_call_mcp(_session, name: str, args: dict) -> str:
        assert name == "search_products"
        assert args["query"] == "monitor"
        return "MON-1: Test Monitor"

    monkeypatch.setattr(
        "meridian_support.agent.list_mcp_tools_openai_format",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "meridian_support.agent.call_mcp_tool",
        fake_call_mcp,
    )

    updated, reply = await run_agent_turn(
        settings=settings,
        openai_client=client,
        mcp_session=AsyncMock(),
        messages=[{"role": "user", "content": "Find a monitor"}],
    )
    assert "monitor" in reply.lower()
    assert any(m.get("role") == "tool" for m in updated)


def test_trim_messages() -> None:
    sys = {"role": "system", "content": "x"}
    rest = [{"role": "user", "content": str(i)} for i in range(50)]
    out = trim_messages_for_storage([sys] + rest, max_messages=10)
    assert len(out) <= 10
    assert out[0]["role"] == "system"
