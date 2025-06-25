import streamlit as st
import requests
import os
from dotenv import load_dotenv

# Load .env variables once at startup
load_dotenv()
API_BASE_URL = os.getenv("CHAT_API_URL", "http://localhost:8001")
CHAT_ENDPOINT = f"{API_BASE_URL}/chat"

# 1) Basic page config
st.set_page_config(page_title="Simple Memory Chat", layout="wide")

# 2) First‐time User ID prompt
if "user_id" not in st.session_state:
    st.session_state.user_id = ""
if not st.session_state.user_id:
    st.title("Enter Your User ID")
    entry = st.text_input("User ID", "")
    if st.button("Continue"):
        if entry.strip():
            st.session_state.user_id = entry.strip()
            st.rerun()
        else:
            st.error("Please enter a non-empty User ID.")
    st.stop()

# 3) Initialize conversation state
if "messages" not in st.session_state:
    st.session_state.messages = []       # list of {"role","content"}
if "awaiting_reply" not in st.session_state:
    st.session_state.awaiting_reply = False

# 4) Sidebar shows your User ID
st.sidebar.markdown(f"**User ID:** {st.session_state.user_id}")

# 5) Title & transcript
st.title("💬 Memory-Enhanced Chatbot")
for msg in st.session_state.messages:
    who = "You" if msg["role"] == "user" else "Bot"
    st.markdown(f"**{who}:** {msg['content']}")

# 6) Input form (only when not waiting for a reply)
if not st.session_state.awaiting_reply:
    with st.form("chat_form", clear_on_submit=True):
        user_input = st.text_input("Your message")
        send = st.form_submit_button("Send")
    if send and user_input:
        # record your message
        st.session_state.messages.append({"role": "user", "content": user_input})
        # block further input until bot responds
        st.session_state.awaiting_reply = True

        # call FastAPI /chat
        try:
            resp = requests.post(
                CHAT_ENDPOINT,
                json={
                    "user_id": st.session_state.user_id,
                    "user_input": user_input
                },
                timeout=15
            )
            resp.raise_for_status()
            bot_reply = resp.json().get("reply", "(no reply)")
        except Exception as e:
            bot_reply = f"Error: {e}"

        # record bot's reply and re‐enable input
        st.session_state.messages.append({"role": "assistant", "content": bot_reply})
        st.session_state.awaiting_reply = False

        # re‐run to show the new reply immediately
        st.rerun()

else:
    st.info("⏳ Waiting for bot response...")

