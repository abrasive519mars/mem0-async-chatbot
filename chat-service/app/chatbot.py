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
        "You are an conversational assistant with memory. "
        "Use the following memories and recent chat to respond in a context-aware, relevant manner.:\n\n"
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

    # Create RFM-aware prompt
    prompt = f"""You are a helpful assistant with access to the user's important memories ranked by recency, frequency, and magnitude.

    Recent Chat History: {history_block}

    Relevant Memories (ranked by RFM score):
    {memories_block}

    Current User Input: {user_input}

    Respond based on the user's most important and recently accessed memories."""

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
        "\n- ".join(rfm_memories)
        if rfm_memories else "No high-RFM memories available."
    )
    semantic_block = (
        "\n- ".join([m["text"] for m in semantic_memories])
        if semantic_memories else "No semantically similar memories found."
    )
    history_block = "\n".join(
        [f"User: {m['user_message']}\nBot: {m['bot_response']}" for m in recent]
    ) if recent else "No chat history."

    # Create comprehensive prompt
    prompt = f"""You are a helpful conversational assistant with access to both semantically relevant memories and the user's most important memories.

    Recent Chat History:
    {history_block}

    Semantically Relevant Memories:
    {semantic_block}

    Important Memories (ranked by RFM):
    {rfm_block}

    Current User Input: {user_input}

    Given all of this, respond in a context aware, relevant manner to the current user input. Using both the conversation context and the most relevant memories from both sources. """


    # 4. Generate response using Gemini
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )

    return response.text.strip()

    
