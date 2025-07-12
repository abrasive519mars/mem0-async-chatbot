# streamlit_ui/config.py
import os
from dotenv import load_dotenv

load_dotenv()  # loads .env from project root

# Base URL of your FastAPI backend; override in .env for production
CHAT_API_URL = os.getenv("CHAT_API_URL", "http://localhost:8080")
