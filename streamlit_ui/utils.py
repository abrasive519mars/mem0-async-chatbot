# streamlit_ui/utils.py
import requests
import streamlit as st
from streamlit import session_state

def send_chat_request(endpoint: str, user_id: str, prompt: str, base_url: str) -> str:
    """POST to the given endpoint and return the reply text (or error)."""
    url = f"{base_url}/{endpoint}"
    try:
        resp = requests.post(
            url,
            json={"user_id": user_id, "user_input": prompt},
            timeout=30
        )
        resp.raise_for_status()
        return resp.json().get("reply", "")
    except Exception as e:
        return f"Error: {e}"

def render_chat_tab(endpoint: str, history_key: str, base_url: str):
    """Display a single Streamlit chat tab with its own history."""
    # Initialize history
    if history_key not in session_state:
        session_state[history_key] = []

    # Display past messages
    for msg in session_state[history_key]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input
    if prompt := st.chat_input(
     "Type your message...", 
     key=f"chat_input_{history_key}"):

        # Show user message
        session_state[history_key].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Get bot reply
        reply = send_chat_request(endpoint, session_state.user_id, prompt, base_url)

        # Show and store assistant message
        session_state[history_key].append({"role": "assistant", "content": reply})
        with st.chat_message("assistant"):
            st.markdown(reply)
