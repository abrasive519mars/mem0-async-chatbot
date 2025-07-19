import os
import json
import asyncio
import numpy as np
from datetime import datetime, timezone
from dotenv import load_dotenv
from google import genai
from google.genai import types
import hnswlib
from supabase import create_client
from redis.commands.search.query import Query
import uuid

from .RFM_functions import get_magnitude_for_query, get_recency_score, get_rfm_score

# Load env variables
load_dotenv()
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

def time_ago_human(past_time_str, now=None):
    now = now or datetime.now(timezone.utc)
    past_time = datetime.fromisoformat(past_time_str.replace('Z', '+00:00'))
    diff = now - past_time

    if diff.days > 365:
        years = diff.days // 365
        return f"{years} year{'s' if years > 1 else ''} ago"
    elif diff.days > 30:
        months = diff.days // 30
        return f"{months} month{'s' if months > 1 else ''} ago"
    elif diff.days > 0:
        return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours} hour{'s' if hours > 1 else ''} ago"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
    else:
        return "just now"


async def fetch_last_m_messages(redis_client, user_id, m=5):
    """
    Retrieve the latest m chat messages for a user, with humanized timestamps.
    """
    # Corrected query string: use actual variable interpolation
    query_str = f"@user_id:{{{user_id}}}"
    query = Query(query_str).sort_by("timestamp", asc=False).paging(0, m)
    res = redis_client.ft("chats_idx").search(query)
    
    now = datetime.now(timezone.utc)
    messages = []
    for doc in res.docs:
        msg = doc.__dict__
        msg['timestamp'] = time_ago_human(msg['timestamp'], now) if 'timestamp' in msg else "unknown"
        messages.append(msg)
    return messages


async def summarize_user_memories(user_id: str) -> str:
    """
    Summarize existing user memories into a concise overview.
    """
    resp = await asyncio.to_thread(
        lambda: supabase.table("persona_category")
                      .select("memory_text")
                      .eq("user_id", user_id)
                      .execute()
    )
    memories = [r["memory_text"] for r in (resp.data or [])]
    if not memories:
        return "No prior memories stored yet."
    joined = "\n- " + "\n- ".join(memories)
    prompt = (
        f"You are a memory summarizer.\n\n"
        f"Known memories:{joined}\n\n"
        "Summarize the user's personality, interests, and preferences in 3–5 lines."
    )
    result = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    return result.text.strip()

async def get_embedding(text: str) -> list[float]:
    """
    Generate a vector embedding for the given text.
    """
    embed_res = client.models.embed_content(
        model="text-embedding-004",
        contents=text,
        config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT")
    )
    return embed_res.embeddings[0].values if embed_res.embeddings else []

def cosine_similarity(a: list[float], b: list[float]) -> float:
    """
    Compute cosine similarity between two vectors.
    """
    v1, v2 = np.array(a), np.array(b)
    if not v1.any() or not v2.any():
        return 0.0
    return float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))

async def get_semantically_similar_memories(
    redis_client, user_id, input_embedding, k=3, bump_metadata=True, cutoff = 0.7
):
    """
    Retrieve top-k semantically similar memories for a user from Redis.
    
    Args:
        redis_client: Your redis-py client (.client from RedisManager)
        user_id (str): The user ID to filter for
        input_embedding (list or np.ndarray): The embedding to compare against
        k (int): How many results to return
        bump_metadata (bool): Increment frequency/set last_used if True
        cutoff (float or None): Skip results with distance > cutoff (if set)
    Returns:
        List of dicts: Each with id, text, sim, created_at, last_used
    """
    # Ensure correct embedding dtype and shape
    vec = np.array(input_embedding, dtype=np.float32)
    if vec.shape[0] != 768:
        raise ValueError(f"Embedding must be length 768, got {vec.shape}")

    # Build RediSearch KNN query with user filter
    query_str = f"@user_id:{{{user_id}}}=>[KNN {k} @embedding $vec as score]"
    params = {"vec": vec.tobytes()}
    query = (
        Query(query_str)
        .return_fields("id", "memory_text", "score", "created_at", "last_used")
        .sort_by("score", asc=True)
        .paging(0, k)
        .dialect(2)
    )

    # Execute the search (in a thread for async compatibility)
    res = await asyncio.to_thread(
        redis_client.ft("memories_idx").search, query, query_params=params
    )
    now_iso = datetime.now(timezone.utc).isoformat()
    results = []
    for doc in res.docs:
        sim_score = float(doc.score)
        if cutoff is not None and sim_score > cutoff:
            continue
        key = f"memories:{user_id}:{doc.id}"
        if bump_metadata:
            redis_client.hincrby(key, "frequency", 1)
            redis_client.hset(key, "last_used", now_iso)
            try:
                freq = int(redis_client.hget(key, "frequency"))
            except:
                freq = 5    
            try:
                magnitude = float(redis_client.hget(key, "magnitude"))
            except (TypeError, ValueError):
                magnitude = 1.0
            recency_timestamp = now_iso
            rfm_score = get_rfm_score(recency_timestamp, freq, magnitude)
            redis_client.hset(key, "rfm_score", rfm_score)


        results.append({
            "id": getattr(doc, "id", None),
            "text": getattr(doc, "memory_text", None),
            "sim": sim_score,
            "created_at": getattr(doc, "created_at", None),
            "last_used": now_iso if bump_metadata else getattr(doc, "last_used", None)
        })
    return results


async def get_highest_rfm_memories(redis_client, user_id, k=3):
    query = f"@user_id:{{{user_id}}}"
    query = Query(query).sort_by("rfm_score", asc=False).paging(0, k)
    res = redis_client.ft("memories_idx").search(query)
    results = []
    for doc in res.docs:
        results.append({
            "id": doc.id,
            "text": doc.memory_text,
            "rfm_score": float(doc.rfm_score) if hasattr(doc, 'rfm_score') else None
        })
    return results



async def generate_candidate_memories(     
    user_id: str,
    user_msg: str,
    bot_resp: str,
) -> list[str]:
    """
    Extract new memories from recent conversation if they contain novel insights.
    """
    
    prompt = f"""
You are a **Memory Extraction Engine**.

TASK ─ Identify **0-2 NEW** user memories found *only* in the exchange below.

RULES
• Start each memory with “- ”.  
• Around **15 words** per memory, third-person, about the *user*.  
• Include specific nouns, verbs, and context words from user's message for better retrieval in the future.  
• Skip if nothing new → output single line: **- None**

CURRENT EXCHANGE (ON WHCIH YOU ARE SUPPOSED TO GENERATE MEMORIES ON)
User: {user_msg}
Bot : {bot_resp}

EXAMPLE OUTPUT 
- Memory one.
- Memory two.

OUTPUT: 
"""


    resp = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
    text = resp.text.strip()
    if text.lower() == "none":
        return []
    return [line.strip("- ").strip() for line in text.split("\n") if line.strip()]

def clean_mem_id(mem_id):
    return mem_id[-36:]


async def update_user_memory(redis_manager, candidate: str, user_id: str, user_msg: str, bot_resp: str) -> str:
    """
    Decide add/merge/override and update Redis accordingly.
    All operations happen in Redis during the session.
    """

    context_pair = f"User: {user_msg}\nBot: {bot_resp}"
    now = datetime.now(timezone.utc).isoformat()
    emb = await get_embedding(candidate)
    sims = await get_semantically_similar_memories(redis_manager.client, user_id, emb, k=3, bump_metadata=False)

    
    alias = {str(i+1): sim["id"] for i, sim in enumerate(sims)}
     
    prompt = f"""
You are a Memory Manager for a chatbot service. Your job is to decide how to integrate a new candidate memory into a chatbot's existing memories. Base your decision solely on the content and meaning of the memories, and on relative semantic similarity scores.

CURRENT EXCHANGE, on which the candidate memory is extracted:
{context_pair}

INPUTS:
• Candidate memory:
  "{candidate}"

• Existing semantically similarmemories (up to 5):
{chr(10).join(f"Index: {i+1} | Text: {sim['text']} | Similarity: {sim['sim']}" for i, sim in enumerate(sims))}

DECISION RULES:
1. OVERRIDE if it fully duplicates or directly contradicts an existing memory.
2. MERGE only if it adds new, non-redundant information to an existing memory.
3. ADD if it is a genuinely new fact or insight not present in any existing memory, or there are no semantically similar memories.
4. NONE if it is redundant or not useful.

OUTPUT (exactly one of the following, no extra text):
add
merge:<index>
override:<index>
none

Examples:
add
merge:1,2
override:3

Do not deviate from this formatting as it will result in your system failing.
"""

    dec = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    ).text.strip().lower()

    if dec == "None":
        return "Redundant, no memory update."
    
    elif dec == "add":
        magnitude = await get_magnitude_for_query(candidate)
        rfm = get_rfm_score(now, frequency=1, magnitude=magnitude)
        emb_bytes = np.array(emb, dtype=np.float32).tobytes()
        mem_id = str(uuid.uuid4())
        memory_dict = {
            "id": mem_id,
            "user_id": user_id,
            "memory_text": candidate,
            "embedding": emb,
            "magnitude": magnitude,
            "last_used": now,
            "frequency": 1,
            "rfm_score": rfm,
            "created_at": now
        }

        redis_manager.store_memory(user_id, mem_id, memory_dict)
        return "Memory added."
        
    elif dec.startswith("merge:"):
        idxs = [i.strip() for i in dec.replace("merge:", "").split(",")]
        merged_log = ""
        for idx in idxs:
            mem_id = alias.get(idx)
            
            current_mem = redis_manager.client.hgetall(f"{mem_id}")
            
            current_text = str(current_mem[b'memory_text'].decode('utf-8'))
            current_freq = int(current_mem[b'frequency'].decode('utf-8'))
            
            merged_text = await llm_consolidate(current_text, candidate)
            emb_new = await get_embedding(merged_text)
            magnitude = await get_magnitude_for_query(merged_text)
            rfm = get_rfm_score(now, frequency=current_freq + 1, magnitude=magnitude)
            memory_dict = {
                "id": clean_mem_id(mem_id),
                "user_id": user_id,
                "memory_text": merged_text,
                "embedding": emb,
                "magnitude": magnitude,
                "last_used": now,
                "frequency": current_freq + 1,
                "rfm_score": rfm,
            }
            
            redis_manager.store_memory(user_id, memory_dict["id"], memory_dict)
            merged_log += f"Memory ID {mem_id} {current_text[:15]} modified to {merged_text[:15]}\n"
        return f"Total {len(idxs)} memories merged for {user_id}:\n" + merged_log  

    elif dec.startswith("override:"):
        idxs = [i.strip() for i in dec.replace("override:", "").split(",")]
        override_log = ""
        for idx in idxs:
            mem_id = alias.get(idx)
            current_mem = redis_manager.client.hgetall(f"{mem_id}")
            current_text = str(current_mem[b'memory_text'].decode('utf-8'))

            current_freq = int(current_mem[b'frequency'].decode('utf-8'))
            magnitude = await get_magnitude_for_query(candidate)
            rfm = get_rfm_score(now, frequency=current_freq + 1, magnitude=magnitude)

            memory_dict = {
                "id": clean_mem_id(mem_id),
                "user_id": user_id,
                "memory_text": candidate,
                "embedding": emb,
                "magnitude": magnitude,
                "last_used": now,
                "frequency": current_freq + 1,
                "rfm_score": rfm,
            }
            redis_manager.store_memory(user_id, memory_dict["id"], memory_dict)
            override_log += f"Memory ID {mem_id} {current_text[:15]} overriden to {candidate[:15]}\n"
        return f"Total {len(idxs)} overriden for {user_id}:\n" + override_log        
    
    return "No memory update." 



async def llm_consolidate(memory: str, candidate: str) -> str:
    prompt = f"""
        You are a Memory Consolidation Agent. Your task is to merge a related user memory
        and a new memory candidate into ONE concise, information-rich memory (**max 20 words, 2 sentences long**).

        ──────────────────────────
        INPUTS
        • Existing memory:
        - {memory}
        • New memory candidate:
        - {candidate}
        ──────────────────────────
IMPORTANT: The merged memory must include all important keywords from the original memory and the candidate.
Do not omit any key terms, names, or topics.

Merged memory (must contain all important keywords):
        """

    res = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
    return res.text.strip()

async def log_message(redis_manager, user_id: str, user_input: str, bot_response: str):
    """
    Persist every user-bot exchange chronologically in Redis.
    """
    # Generate a unique chat ID
    chat_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    # Build the chat record
    chat_record = {
        "id": chat_id,
        "user_id": user_id,
        "user_message": user_input,
        "bot_response": bot_response,
        "timestamp": timestamp,
    }

    redis_manager.store_chat(user_id, chat_id, chat_record)
    

