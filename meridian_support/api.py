"""FastAPI orchestration — chat endpoint bridges OpenAI and MCP."""

from __future__ import annotations

import asyncio
import logging
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai import AsyncOpenAI
from pydantic import BaseModel, Field, field_validator

from meridian_support.agent import run_agent_turn, trim_messages_for_storage
from meridian_support.config import Settings, get_settings
from meridian_support.mcp_bridge import list_mcp_tools_openai_format, mcp_client_session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    """OpenAI-style messages; may include tool_calls and tool for full history."""

    messages: list[dict[str, Any]] = Field(..., min_length=1)
    session_id: str | None = Field(
        default=None,
        description="Optional client session id for logging (no server-side state)",
    )

    @field_validator("messages")
    @classmethod
    def each_message_has_role(cls, v: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for i, m in enumerate(v):
            if not isinstance(m, dict) or "role" not in m:
                raise ValueError(f"messages[{i}] must be an object with 'role'")
        return v


class ChatResponse(BaseModel):
    messages: list[dict[str, Any]]
    reply: str


def create_app() -> FastAPI:
    app = FastAPI(
        title="Meridian Support API",
        description="Customer support orchestration: GPT-4o-mini + MCP (inventory, orders, customers)",
        version="0.1.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    async def health_ready(settings: Annotated[Settings, Depends(get_settings)]) -> dict[str, Any]:
        """Verify MCP server is reachable (for probes before demos)."""
        try:
            async with asyncio.timeout(15.0):
                async with mcp_client_session(str(settings.mcp_server_url)) as session:
                    tools = await list_mcp_tools_openai_format(session)
            return {
                "status": "ok",
                "mcp": "connected",
                "tool_count": len(tools),
            }
        except Exception as exc:  # noqa: BLE001
            logger.exception("MCP readiness check failed")
            raise HTTPException(
                status_code=503,
                detail={"mcp": "unreachable", "error": str(exc)},
            ) from exc

    @app.post("/v1/chat", response_model=ChatResponse)
    async def chat(
        body: ChatRequest,
        settings: Annotated[Settings, Depends(get_settings)],
    ) -> ChatResponse:
        if not settings.openai_api_key:
            raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not configured")

        user_tail = [m for m in body.messages if m.get("role") == "user"]
        if not user_tail:
            raise HTTPException(status_code=400, detail="At least one user message is required")

        openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
        history = trim_messages_for_storage(list(body.messages))

        try:
            async with asyncio.timeout(settings.request_timeout_seconds):
                async with mcp_client_session(str(settings.mcp_server_url)) as mcp_session:
                    updated, reply = await run_agent_turn(
                        settings=settings,
                        openai_client=openai_client,
                        mcp_session=mcp_session,
                        messages=history,
                    )
        except TimeoutError as exc:
            logger.exception("Chat request timed out session_id=%s", body.session_id)
            raise HTTPException(status_code=504, detail="Request timed out") from exc
        except Exception as exc:  # noqa: BLE001
            logger.exception("Chat failed session_id=%s", body.session_id)
            raise HTTPException(status_code=502, detail=f"Upstream error: {exc}") from exc

        return ChatResponse(messages=updated, reply=reply)

    return app


app = create_app()
