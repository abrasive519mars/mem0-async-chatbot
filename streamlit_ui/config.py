import os
from dotenv import load_dotenv

# Load .env at project root
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

# Base URL for your FastAPI chat service
API_BASE_URL = os.getenv("CHAT_API_URL", "http://localhost:8001")

# Endpoints for synchronous chat and health check
ENDPOINTS = {
    "chat": f"{API_BASE_URL}/chat",
    "health": f"{API_BASE_URL}/"
}

# UI text and defaults
APP_TITLE = "🤖 Memory-Enhanced Chatbot"
APP_DESCRIPTION = "Chat with an AI that remembers your preferences and past conversations"
DEFAULT_USER_ID = "demo_user"
