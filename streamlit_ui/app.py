import streamlit as st
import time
from utils import render_chat_tab, get_user_memories_from_redis
from config import CHAT_API_URL

st.set_page_config(
    page_title="Memory-Enhanced Chatbot",
    page_icon="🤖",
    layout="wide"
)

# --- Login Screen ---
if "user_id" not in st.session_state or not st.session_state["user_id"]:
    st.title("Login")
    user_id_input = st.text_input("Enter your User ID to login")
    if st.button("Login") and user_id_input.strip():
        st.session_state["user_id"] = user_id_input.strip()
        st.rerun()
    st.stop()

# --- Sidebar: Logout and View Memories ---
with st.sidebar:
    st.title("User Settings")
    st.markdown(f"**User ID:** {st.session_state['user_id']}")
    if st.button("Logout"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
    st.markdown("---")
    if st.button("View My Memories"):
        st.session_state["show_memories"] = True

# --- Sidebar: User Memories Viewer (from Redis) ---
if st.session_state.get("show_memories"):
    st.sidebar.markdown("### 🧠 Your Memories")
    memories = get_user_memories_from_redis(st.session_state["user_id"])
    if memories is None:
        st.sidebar.info("User memory viewing via Redis is coming soon!")
    elif not memories:
        st.sidebar.info("No memories found for this user.")
    else:
        for mem in memories:
            st.sidebar.markdown(f"- {mem.get('memory_text', str(mem))}")
    if st.sidebar.button("Close Memories"):
        st.session_state["show_memories"] = False

st.title(f"💬 Chatbot Dashboard — User: {st.session_state['user_id']}")

# --- Main Tabs for Chat Endpoints ---
tabs = st.tabs([
    "🔍 Semantic Memory",
    "📊 RFM Only",
    "🔗 RFM + Semantic"
])
endpoints = ["chat-semantic", "chat-rfm", "chat-rfm-semantic"]
history_keys = ["semantic_history", "rfm_history", "combined_history"]

for tab, ep, key in zip(tabs, endpoints, history_keys):
    with tab:
        start_time = time.perf_counter()
        chat_response = render_chat_tab(ep, key, CHAT_API_URL)
        elapsed = time.perf_counter() - start_time
        st.markdown(
            f"<div style='text-align: right; font-size: 12px; color: gray;'>"
            f"⏱️ Response time: {elapsed:.2f} seconds</div>",
            unsafe_allow_html=True
        )
