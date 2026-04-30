# Hugging Face Spaces (Docker) or any container host — Streamlit UI + FastAPI API.
FROM python:3.12-slim

WORKDIR /app

# https://docs.astral.sh/uv/guides/integration/docker/#using-uv-in-docker
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MERIDIAN_API_URL=http://127.0.0.1:8000

COPY uv.lock pyproject.toml ./
COPY meridian_support ./meridian_support
COPY streamlit_app.py .

RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

COPY docker-entrypoint.sh .
RUN chmod +x docker-entrypoint.sh

# Render/HF inject PORT; EXPOSE is advisory (Streamlit binds 0.0.0.0:$PORT).
EXPOSE 10000

# HF Spaces sets PORT; Streamlit should listen there for the public URL.
ENTRYPOINT ["./docker-entrypoint.sh"]
