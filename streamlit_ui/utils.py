import requests
import streamlit as st
from .config import ENDPOINTS

def check_api_health() -> bool:
    """Returns True if the chat service is responding."""
    try:
        r = requests.get(ENDPOINTS["health"], timeout=3)
        return r.status_code == 200
    except:
        return False

def call_chat_api(user_input: str, user_id: str) -> str:
    """Sends the user input to /chat and returns the bot's full reply."""
    payload = {"user_id": user_id, "user_input": user_input}
    try:
        r = requests.post(ENDPOINTS["chat"], json=payload, timeout=30)
        r.raise_for_status()
        return r.json().get("reply", "No reply received.")
    except requests.exceptions.Timeout:
        return "⚠️ Request timed out. Please try again."
    except requests.exceptions.ConnectionError:
        return "⚠️ Cannot connect to chat service."
    except Exception as e:
        return f"❌ Error: {e}"
