from dotenv import load_dotenv
import os
from google import genai

load_dotenv()

# Test the new SDK
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

try:
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents="Hello! This is a test of the new Google Gen AI SDK."
    )
    print("✅ New Google Gen AI SDK working!")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"❌ Error with new SDK: {e}")
