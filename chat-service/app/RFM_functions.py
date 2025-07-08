from google import genai
import asyncio
from datetime import datetime, timezone
from dotenv import load_dotenv
import os

load_dotenv()    

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))


#Magnitude function
async def get_magnitude_for_query(prompt: str) -> float:

    prompt_text = f"""
You are an expert assistant evaluating how important or urgent a given user prompt is.

Rate the importance of the following prompt on a scale from 0 (not important) to 5 (very important), using your own reasoning:

Focus on the user's point of view, not external facts.

Messages that are highly personal, emotionally significant, or reveal things the user would typically share only with someone close should score higher.

Messages that are informative about the user — such as their preferences, goals, values, or memories — also warrant a higher score.

General, casual, or non-personal messages should score lower.

Prompt: "{prompt}"

Only output a single number between 0 and 5.
"""

    try:
        response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt_text)
        magnitude = float(response.text.strip())
        return round(max(0, min(5, magnitude)), 2)
    except Exception as e:
        return 0.0



#Recency Function
def get_recency_score(timestamp_input) -> int:
    """
    Computes a recency score (1-5) based on how many days ago the timestamp was.
    Accepts either a datetime object or an ISO 8601 string.
    """
    # Convert string to datetime if needed
    if isinstance(timestamp_input, str):
        try:
            timestamp = datetime.fromisoformat(timestamp_input)
        except ValueError:
            # In case the string isn't fully ISO (like missing offset)
            timestamp = datetime.strptime(timestamp_input[:10], "%Y-%m-%d")
    elif isinstance(timestamp_input, datetime):
        timestamp = timestamp_input
    else:
        raise TypeError("timestamp_input must be a string or datetime object")

    # Ensure timezone-aware datetime (assume UTC if missing tzinfo)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    days_ago = (now - timestamp).days

    # Return score based on how many days ago
    if days_ago <= 1:
        return 5
    elif days_ago <= 3:
        return 4
    elif days_ago <= 7:
        return 3
    elif days_ago <= 14:
        return 2
    else:
        return 1

#RFM score function
def get_rfm_score(recency_timestamp: str, frequency: int, magnitude: float) -> float:
    recency_score = get_recency_score(recency_timestamp)  # Uses existing recency function
    rfm_score = recency_score * 0.3 + frequency * 0.2 + magnitude * 0.5
    return round(rfm_score, 2)

