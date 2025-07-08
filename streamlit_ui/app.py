# streamlit_ui/app.py
import streamlit as st
from config import CHAT_API_URL
from utils import render_chat_tab

st.set_page_config(
    page_title="Memory-Enhanced Chatbot",
    page_icon="🤖",
    layout="wide"
)

# 1. Prompt for user_id on first load
if "user_id" not in st.session_state:
    st.title("🔐 Enter User ID")
    uid = st.text_input("User ID")
    if uid:
        st.session_state.user_id = uid
        st.rerun()  # Changed from st.experimental_rerun()
    st.stop()

st.title(f"💬 Chatbot Dashboard — User: {st.session_state.user_id}")

# 2. Tabs for each endpoint
tabs = st.tabs(["🔍 Semantic Memory", "📊 RFM Only", "🔗 RFM + Semantic"])
endpoints = ["chat-semantic", "chat-rfm", "chat-rfm-semantic"]
history_keys = ["semantic_history", "rfm_history", "combined_history"]

# 3. Render each tab
for tab, ep, key in zip(tabs, endpoints, history_keys):
    with tab:
        render_chat_tab(ep, key, CHAT_API_URL)
