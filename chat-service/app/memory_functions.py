# memory-worker/memory_functions.py

import os
import json
import asyncio
import numpy as np
from datetime import datetime, timezone
from dotenv import load_dotenv
from google import genai
from google.genai import types
from supabase import create_client

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


async def fetch_last_m_messages(user_id: str, m: int = 5):
    """
    Fetch the last m chat messages for context, returning only a humanized timestamp.
    """
    resp = await asyncio.to_thread(
        lambda: supabase.table("chat_message_logs")
                        .select("user_message, bot_response, timestamp")
                        .eq("user_id", user_id)
                        .order("timestamp", desc=True)
                        .limit(m)
                        .execute()
    )
    msgs = resp.data or []
    now = datetime.now(timezone.utc)
    for msg in msgs:
        if 'timestamp' in msg and msg['timestamp']:
            msg['timestamp'] = time_ago_human(msg['timestamp'], now)
        else:
            msg['timestamp'] = 'unknown'
    msgs.reverse()  # Oldest first
    return msgs

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
    user_id: str,
    candidate: str,                # Make sure to pass your Supabase client
    top_k: int = 3,
    threshold: float = 0.7
) -> list[dict]:
    """
    Retrieve up to top_k existing memories semantically similar to candidate using Supabase vector search.
    """
    # 1. Generate the embedding for the candidate memory
    emb = await get_embedding(candidate)  # Should return a list/array of floats

    # 2. Call the Supabase RPC function (runs in the database, uses HNSW index)
    result = await asyncio.to_thread(
        lambda: supabase.rpc(
            "get_similar_memories",
            {
                "query_embedding": emb,
                "target_user_id": user_id,
                "similarity_threshold": threshold,
                "max_results": top_k
            }
        ).execute()
    )

    now = datetime.now(timezone.utc)
    memories = []
    for row in (result.data or []):
      memories.append({
            "id": row["id"],
            "text": row["memory_text"],
            "sim": row["similarity_score"],
            "created_at": time_ago_human(row.get("created_at"), now) if row.get("created_at") else "unknown",
            "last_used": time_ago_human(row.get("last_used"), now) if row.get("last_used") else "unknown"
        })
    return memories
    



async def get_highest_rfm_memories(user_id: str, top_k: int) -> list[str]:
    """
    Return top_k memory_texts with the highest RFM scores for the given user.
    """
    result = await asyncio.to_thread(
        lambda: supabase.table("persona_category")
                        .select("memory_text", "frequency", "magnitude", "rfm_score")
                        .eq("user_id", user_id)
                        .order("rfm_score", desc=True)
                        .limit(top_k)
                        .execute()
    )

    memories = []
    for row in (result.data or []):
      memories.append({
            "text": row["memory_text"],
            "frequency": row["frequency"],
            "magnitude": row["magnitude"],
            "rfm_score": row["rfm_score"]
        })
    return memories



async def generate_candidate_memories(
    user_id: str,
    user_msg: str,
    bot_resp: str,
    m: int = 5
) -> list[str]:
    """
    Extract new memories from recent conversation if they contain novel insights.
    """
    last_msgs_task =  fetch_last_m_messages(user_id, m)
    summary_task =  summarize_user_memories(user_id)
    last_msgs, summary = await asyncio.gather(last_msgs_task, summary_task)
    chat_hist = "\n".join([f"User: {c['user_message']}\nBot: {c['bot_response']}" for c in last_msgs])
    summary_indented = summary.replace("\n", "\n     ")
    chat_hist_indented = chat_hist.replace("\n", "\n     ")

    prompt = f"""
You are a Memory Extraction Engine. Your sole task is to extract up to TWO novel memories *directly* from the current exchange. Use the summary and recent chat history as background context for generating the candidate memory.

1. CONTEXT (for reference only):
• Profile Summary:  
    {summary_indented}
• Recent History (last {m} turns):  
    {chat_hist_indented}

2. CURRENT EXCHANGE (use only this for generating memories):
User: {user_msg}
Bot:  {bot_resp}

3. MEMORY GENERATION RULES:
• Generate 0–2 bullet points, each starting with “- ”.
• Each memory must be a single, complete, third-person sentence about the user.
• Each memory must be exactly 15 words long.
• Each memory must include all important keywords from the user's statements to maximize semantic retrievability.
• Be specific: include details (what, when, why, how) if present.
• Extract any memory that is present in the current exchange, even if it is similar to existing memories. Repeated topics are valuable for tracking frequency and recency.
• Use key nouns and verbs from the user's statements.
• If the user contradicts a previous memory, phrase the new memory to reflect the update.
• If no new memory, output exactly “- None”.

4. OUTPUT FORMAT:
- Memory sentence one.
- Memory sentence two.

Now, generate the memories based on the CURRENT EXCHANGE.
"""


    resp = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
    text = resp.text.strip()
    if text.lower() == "none":
        return []
    return [line.strip("- ").strip() for line in text.split("\n") if line.strip()]

async def update_user_memory(candidate: str, user_id: str, user_msg: str, bot_resp: str) -> str:
    """
    Decide add/merge/override and update Supabase accordingly.
    """
    context_pair = f"User: {user_msg}\nBot: {bot_resp}"
    now = datetime.now(timezone.utc).isoformat()
    sims = await get_semantically_similar_memories(user_id, candidate)
    alias = {str(i+1): sim["id"] for i, sim in enumerate(sims)}
    formatted = [f"[{i+1}] {sim["text"]}" for i, sim in enumerate(sims)]
    if not sims:
        emb = await get_embedding(candidate)
        magnitude = await get_magnitude_for_query(candidate)
        rfm = get_rfm_score(now, frequency=1, magnitude=magnitude)
        await asyncio.to_thread(
            lambda: supabase.table("persona_category")
                          .insert({"user_id":user_id,"memory_text":candidate,"embedding":json.dumps(emb), "magnitude": magnitude, "last_used": now, "frequency": 1, "rfm_score": rfm})
                          .execute()
        )
        return "Memory added."
    prompt = f"""
You are a Memory Manager service. Your job is to decide how to integrate a new candidate memory into a user's existing memories. Base your decision solely on the content and meaning of the memories, and on relative semantic similarity scores.

CURRENT EXCHANGE, on which the candidate memory is extracted:
{context_pair}

INPUTS:
• Candidate memory:
  "{candidate}"

• Existing memories (up to 5):
{chr(10).join(f"Index: {i+1} | Text: {sim['text']} | Similarity: {sim['sim']}" for i, sim in enumerate(sims))}

DECISION RULES:
1. OVERRIDE if it fully duplicates or directly contradicts an existing memory.
2. MERGE only if it adds new, non-redundant information to an existing memory.
3. ADD if it is a genuinely new fact or insight not present in any existing memory.
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


    dec = client.models.generate_content(model="gemini-2.5-flash", contents=prompt).text.strip().lower()
    if dec == "add":
        emb = await get_embedding(candidate)
        magnitude = await get_magnitude_for_query(candidate)
        rfm = get_rfm_score(now, frequency=1, magnitude=magnitude)
        await asyncio.to_thread(
            lambda: supabase.table("persona_category")
                          .insert({"user_id":user_id,"memory_text":candidate,"embedding":json.dumps(emb), "magnitude": magnitude, "last_used": now, "frequency": 1, "rfm_score": rfm})
                          .execute()
        )
        return "Memory added."
    if dec.startswith("merge:"):
        idxs = [i.strip() for i in dec.replace("merge:","").split(",")]
        for idx in idxs:
            id_ = alias.get(idx)
            if id_:
                existing_row = await asyncio.to_thread(
                    lambda: supabase.table("persona_category")
                                .select("frequency")
                                .eq("id", id_)
                                .single()
                                .execute()
                )
                existing_freq = existing_row.data.get("frequency", 1)

                mem_to_merge = sims[int(idx)-1]["text"]
                
                merged = await llm_consolidate(mem_to_merge, candidate)
                emb = await get_embedding(merged)
                magnitude = await get_magnitude_for_query(merged)
                rfm = get_rfm_score(now, frequency= existing_freq, magnitude=magnitude)
                await asyncio.to_thread(
                    lambda: supabase.table("persona_category")
                                .update({"memory_text":merged,"embedding":json.dumps(emb), "magnitude": magnitude, "last_used": now, "frequency": existing_freq, "rfm_score": rfm})
                                .eq("id", id_).execute())                

        return f"Merged with {len(idxs)} as new memories"
    if dec.startswith("override:"):
        idxs = [i.strip() for i in dec.replace("override:","").split(",")]
        emb = await get_embedding(candidate)
        magnitude = await get_magnitude_for_query(candidate)
        for idx in idxs:
            id_ = alias.get(idx)
            if id_:
                existing_row = await asyncio.to_thread(
                    lambda: supabase.table("persona_category")
                                .select("frequency")
                                .eq("id", id_)
                                .single()
                                .execute()
                )
                existing_freq = existing_row.data.get("frequency", 1)

                rfm = get_rfm_score(now, frequency= existing_freq, magnitude=magnitude)
                
                await asyncio.to_thread(
                    lambda: supabase.table("persona_category")
                                  .update({"memory_text":candidate,"embedding":json.dumps(emb), "magnitude": magnitude, "last_used": now, "frequency": existing_freq +1, "rfm_score": rfm})
                                  .eq("id", id_).execute()
                )
        return f"Overridden {len(idxs)}"
    return "No action taken."

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

async def log_message(user_id: str, user_input: str, bot_response: str):
    """
    Persist every user-bot exchange chronologically.
    """
    await asyncio.to_thread(
        lambda: supabase.table("chat_message_logs")
                      .insert({
                          "user_id": user_id,
                          "user_message": user_input,
                          "bot_response": bot_response,
                          "timestamp": datetime.now(timezone.utc).isoformat()
                      })
                      .execute()                  
    )