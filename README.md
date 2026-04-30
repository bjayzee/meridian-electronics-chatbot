# Meridian Electronics — AI Customer Support Agent

Production-minded prototype: **Streamlit** chat UI, **FastAPI** orchestration, **OpenAI GPT-4o-mini** with tool calling, and **MCP (Streamable HTTP)** for inventory, orders, and customer systems.

## Architecture

- **Streamlit** (`streamlit_app.py`) — chat UI; calls the API over HTTP (no secrets in the browser).
- **FastAPI** (`meridian_support/api.py`) — `/v1/chat` runs one agent turn: OpenAI chat completions + MCP tool execution in a loop until the model finishes or a round limit is hit.
- **MCP** (`meridian_support/mcp_bridge.py`) — connects to the internal MCP endpoint, lists tools, executes `call_tool`, maps results to text for the model.
- **Agent** (`meridian_support/agent.py`) — system prompt for Meridian support policies (verification before account actions, no invented SKUs).

Environment variables are loaded via `pydantic-settings` (see `.env.example`).

## MCP tools (discovered from server)

The bot drives whatever the server exposes; the Meridian backend includes roughly:

- Products: `list_products`, `get_product`, `search_products`
- Customers: `get_customer`, `verify_customer_pin`
- Orders: `list_orders`, `get_order`, `create_order`

## Local development

**1. Install [uv](https://docs.astral.sh/uv/getting-started/installation/)** (if you do not have it yet).

**2. Dependencies** — from the repo root, using the lockfile:

```bash
uv sync --extra dev
```

This creates `.venv` and installs the app in editable mode with dev tools (e.g. pytest).

**3. Configuration**

Copy `.env.example` to `.env` and set `OPENAI_API_KEY`. Optional: `MCP_SERVER_URL`.

**4. Run the API**

```bash
uv run uvicorn meridian_support.api:app --reload --host 0.0.0.0 --port 8000
```

**5. Run Streamlit**

```bash
uv run streamlit run streamlit_app.py
```

Open the Streamlit URL; set **API base URL** to `http://127.0.0.1:8000` if prompted.

**Health checks**

- `GET /health` — process up.
- `GET /health/ready` — MCP server reachable and tools listed (uses live network).

## Tests

```bash
uv run pytest tests
```


## Deployment (Render)

The same **Docker** image works on [Render](https://render.com) as a **Web Service** (public URL is Streamlit; FastAPI stays on `127.0.0.1:8000` inside the container).


## Security notes for production review

- **Secrets**: OpenAI key only on the server; never embed in Streamlit or client bundles if you split deployments.
- **PIN handling**: `verify_customer_pin` arguments are redacted in server logs; still avoid logging full request bodies in shared middleware.
- **Transport**: MCP URL is HTTPS; keep TLS verification on (default `httpx`).
- **Hardening**: Add API authentication, rate limits, and abuse monitoring before a public launch.

## Cost

Uses **gpt-4o-mini** by default to keep per-conversation cost low; adjust `OPENAI_MODEL` if the business approves a different tier.
