from google import genai
import os

from .memory_functions import fetch_last_m_messages, get_semantically_similar_memories, get_highest_rfm_memories

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
    return response.text.strip()

async def get_bot_response_rfm(user_id: str, user_input: str) -> str:
    # 1. Fetch recent chat history
    recent = await fetch_last_m_messages(user_id, m=5)

    # 2. Fetch top 3 highest RFM score memories
    top_memories = await get_highest_rfm_memories(user_id=user_id, top_k=3)

    memories_block = (
        "\n- " + "\n- ".join(str(m) for m in top_memories)
        if top_memories else "No high RFM memories available."
    )

    # 3. Construct the LLM prompt
    history_block = "\n".join(
        [f"User: {r['user_message']}\nBot: {r['bot_response']}" for r in recent]
    )

    prompt = (
        "You are an assistant with memory. "
        "Use the following high-RFM memories and recent chat to respond:\n\n"
        f"Top Memories:\n{memories_block}\n\n"
        f"Recent Chat:\n{history_block}\n\n"
        f"User: {user_input}\nBot:"
    )

    # 4. Generate the response
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )

    return response.text.strip()



async def get_bot_response_combined(user_id: str, user_input: str) -> str:
    # 1. Fetch recent chat history
    recent = await fetch_last_m_messages(user_id, m=5)

    # 2. Fetch top RFM memories
    rfm_memories = await get_highest_rfm_memories(user_id, top_k=3)

    # 3. Fetch top semantic memories based on current user input
    semantic_memories = await get_semantically_similar_memories(user_id, user_input, top_k=3)

    # === Format memory blocks ===
    rfm_block = (
        "\n- " + "\n- ".join([m["memory_text"] for m in rfm_memories])
        if rfm_memories else "No high-RFM memories available."
    )
    semantic_block = (
        "\n- " + "\n- ".join([m["text"] for m in semantic_memories])
        if semantic_memories else "No semantically similar memories found."
    )
    history_block = "\n".join(
        [f"User: {m['user_message']}\nBot: {m['bot_response']}" for m in recent]
    ) if recent else "No chat history."

    # === Construct prompt ===
    prompt = f"""You are a helpful assistant with memory.
            Use the following three sources of context to reply to the user.
            
            RFM-Based Important Memories: {rfm_block}
            
            Semantically Similar Memories: {semantic_block}
            
            Recent Chat History: {history_block}

            User: {user_input}
            Bot:"""

    # 4. Generate response using Gemini
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )

    return response.text.strip()

    
