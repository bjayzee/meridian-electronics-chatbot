#!/usr/bin/env bash
set -euo pipefail

PORT="${PORT:-8501}"

uvicorn meridian_support.api:app --host 127.0.0.1 --port 8000 &
exec streamlit run streamlit_app.py \
  --server.port="${PORT}" \
  --server.address=0.0.0.0 \
  --browser.gatherUsageStats=false
