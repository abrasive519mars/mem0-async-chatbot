from google import genai
import os

from .memory_functions import fetch_last_m_messages, get_semantically_similar_memories

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))


async def get_bot_response_from_memory(user_id: str, user_input: str) -> str:
    # 1. Fetch recent chat history
    recent = await fetch_last_m_messages(user_id, m=5)
    # 2. Retrieve top-3 semantically similar memories
    sims = await get_semantically_similar_memories(user_id, user_input, top_k=3)
    memories_block = (
        "\n- " + "\n- ".join([m["text"] for m in sims])
        if sims else "No relevant memories."
    )
    # 3. Construct the LLM prompt
    history_block = "\n".join(
        [f"User: {r['user_message']}\nBot: {r['bot_response']}" for r in recent]
    )
    prompt = (
        "You are an assistant with memory. "
        "Use the following memories and recent chat to respond:\n\n"
        f"Memories:\n{memories_block}\n\n"
        f"Recent Chat:\n{history_block}\n\n"
        f"User: {user_input}\nBot:"
    )
    # 4. Generate the response
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    return response.text
