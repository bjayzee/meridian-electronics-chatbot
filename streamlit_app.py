from __future__ import annotations

import os
import uuid

import httpx
import streamlit as st

# In Docker/Render, Dockerfile sets this to the co-located FastAPI process.
DEFAULT_API = os.environ.get("MERIDIAN_API_URL", "http://127.0.0.1:8000")

_FETCH_REPLY_KEY = "_fetch_reply_pending"


# Build user-visible UI.
def _compact_display(messages: list[dict]) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for m in messages:
        role = m.get("role")
        if role == "user" and m.get("content"):
            rows.append(("user", str(m["content"])))
        elif role == "assistant":
            c = m.get("content")
            if c:
                rows.append(("assistant", str(c)))
    return rows


def _chat_styles() -> None:
    st.markdown(
        """
        <style>
        /* User bubbles: align block to the right */
        div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatar-user"]) {
            flex-direction: row-reverse;
            background-color: rgba(25, 118, 210, 0.08);
            border-radius: 12px;
            padding: 0.5rem 0.75rem;
            margin-left: 15%;
        }
        div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatar-user"]) p {
            text-align: right;
        }
        /* Assistant: keep readable width on the left */
        div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatar-assistant"]) {
            background-color: rgba(100, 100, 100, 0.06);
            border-radius: 12px;
            padding: 0.5rem 0.75rem;
            margin-right: 10%;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


st.set_page_config(
    page_title="Meridian Support",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded",
)

_chat_styles()

st.markdown("### Meridian Electronics Support Agent")
st.caption(
    "Ask about products, availability, orders, and account help. "
    "For your orders, verify with email and your 4-digit PIN when prompted."
)

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "backend_messages" not in st.session_state:
    st.session_state.backend_messages = []

api_base = st.sidebar.text_input("API base URL", value=DEFAULT_API)
if st.sidebar.button("Clear conversation"):
    st.session_state.backend_messages = []
    st.session_state.pop(_FETCH_REPLY_KEY, None)
    st.rerun()

try:
    r = httpx.get(f"{api_base.rstrip('/')}/health", timeout=5.0)
    sidebar_health = "Backend: OK" if r.status_code == 200 else f"Backend: HTTP {r.status_code}"
except Exception as exc:  # noqa: BLE001
    sidebar_health = f"Backend: unreachable ({exc})"
st.sidebar.caption(sidebar_health)

# Wide split: transcript (main) vs. optional helper column so chat is not one cramped column
col_chat, col_side = st.columns([2.2, 1.0], gap="large")

with col_side:
    st.markdown("**Tips**")
    st.markdown(
        "- Ask for products by name or category.\n"
        "- For **your** orders, sign in with email + PIN when asked.\n"
        "- SKU examples often look like `MON-0054`."
    )

with col_chat:
    for role, text in _compact_display(st.session_state.backend_messages):
        with st.chat_message("user" if role == "user" else "assistant"):
            st.markdown(text)

    if st.session_state.pop(_FETCH_REPLY_KEY, False):
        payload = {
            "messages": st.session_state.backend_messages,
            "session_id": st.session_state.session_id,
        }
        try:
            with st.chat_message("assistant"):
                with st.spinner("Thinking…"):
                    resp = httpx.post(
                        f"{api_base.rstrip('/')}/v1/chat",
                        json=payload,
                        timeout=180.0,
                    )
            if resp.status_code == 200:
                data = resp.json()
                st.session_state.backend_messages = data.get(
                    "messages", st.session_state.backend_messages
                )
            else:
                err = resp.text
                try:
                    detail = resp.json().get("detail")
                    err = detail if detail else err
                except Exception:  # noqa: BLE001
                    pass
                msg = f"Sorry — something went wrong ({resp.status_code}): {err}"
                st.session_state.backend_messages = st.session_state.backend_messages + [
                    {"role": "assistant", "content": msg},
                ]
        except httpx.TimeoutException:
            msg = "The request timed out. Please try again in a moment."
            st.session_state.backend_messages = st.session_state.backend_messages + [
                {"role": "assistant", "content": msg},
            ]
        except Exception as exc:  # noqa: BLE001
            msg = f"Network error: {exc}"
            st.session_state.backend_messages = st.session_state.backend_messages + [
                {"role": "assistant", "content": msg},
            ]
        st.rerun()

    prompt = st.chat_input("How can we help you today?")
    if prompt:
        st.session_state.backend_messages = st.session_state.backend_messages + [
            {"role": "user", "content": prompt},
        ]
        st.session_state[_FETCH_REPLY_KEY] = True
        st.rerun()
