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

async def fetch_last_m_messages(user_id: str, m: int = 5):
    """
    Fetch the last m chat messages for context without blocking the event loop.
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
    msgs.reverse()
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
    candidate: str,
    top_k: int = 3,
    threshold: float = 0.5
) -> list[dict]:
    """
    Retrieve up to top_k existing memories semantically similar to candidate.
    """
    emb = await get_embedding(candidate)
    resp = await asyncio.to_thread(
        lambda: supabase.table("persona_category")
                      .select("id, memory_text, embedding")
                      .eq("user_id", user_id)
                      .execute()
    )
    sims = []
    for mem in (resp.data or []):
        raw = mem["embedding"]
        vec = json.loads(raw) if isinstance(raw, str) else raw
        score = cosine_similarity(emb, vec)
        if score >= threshold:
            sims.append({"id": mem["id"], "text": mem["memory_text"], "sim": score})
    sims.sort(key=lambda x: x["sim"], reverse=True)
    return sims[:top_k]


async def get_highest_rfm_memories(user_id: str, top_k: int) -> list[str]:
    """
    Return top_k memory_texts with the highest RFM scores for the given user.
    """
    resp = await asyncio.to_thread(
        lambda: supabase.table("persona_category")
                        .select("memory_text")
                        .eq("user_id", user_id)
                        .order("RFM_score", desc=True)
                        .limit(top_k)
                        .execute()
    )

    return [row["memory_text"] for row in (resp.data or [])]



async def generate_candidate_memories(
    user_id: str,
    user_msg: str,
    bot_resp: str,
    m: int = 5
) -> list[str]:
    """
    Extract new memories from recent conversation if they contain novel insights.
    """
    last_msgs = await fetch_last_m_messages(user_id, m)
    summary = await summarize_user_memories(user_id)
    chat_hist = "\n".join([f"User: {c['user_message']}\nBot: {c['bot_response']}" for c in last_msgs])
    summary_indented = summary.replace("\n", "\n     ")
    chat_hist_indented = chat_hist.replace("\n", "\n     ")

    prompt = f"""
    You are a Memory Extraction Engine. Your sole task is to extract up to TWO novel memories *directly* from the current interaction. Use the summary and recent history only as background context—do not let them infulence memory content too much, to avoid repeats. Format your output precisely so it can be parsed with:

        return [line.strip("-• ").strip() for line in text.split("\n") if line.strip()]

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
    • Each bullet must be one sentence, 5–12 words long—very concise.
    • Focus solely on *new*, specific insights from the CURRENT EXCHANGE.
    • Craft each sentence so it maximizes semantic overlap with potential future user queries.
    • If no new memory, output exactly “- None”.

    4. OUTPUT FORMAT:
    -• Memory sentence one.
    -• Memory sentence two.

    Examples:
    -• Discovered passion for painting abstract watercolor landscapes today.
    -• Wants project updates delivered every morning via email.

    Now, generate the memories based on the CURRENT EXCHANGE.
    """


    resp = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
    text = resp.text.strip()
    if text.lower() == "none":
        return []
    return [line.strip("-• ").strip() for line in text.split("\n") if line.strip()]

async def update_user_memory(candidate: str, user_id: str) -> str:
    """
    Decide add/merge/override and update Supabase accordingly.
    """
    now = datetime.now(timezone.utc).isoformat()
    sims = await get_semantically_similar_memories(user_id, candidate)
    alias = {str(i+1): sim["id"] for i, sim in enumerate(sims)}
    formatted = [f"[{i+1}] {sim['text']}" for i, sim in enumerate(sims)]
    if not sims:
        emb = await get_embedding(candidate)
        magnitude = await get_magnitude_for_query(candidate)
        rfm = get_rfm_score(now, frequency=1, magnitude=magnitude)
        await asyncio.to_thread(
            lambda: supabase.table("persona_category")
                          .insert({"user_id":user_id,"memory_text":candidate,"embedding":json.dumps(emb), "magnitude": magnitude, "last_used": now, "frequency": 1, "RFM_score": rfm})
                          .execute()
        )
        return "Memory added."
    prompt = f"""
You are a Memory Manager service responsible for integrating a new memory candidate into a user’s existing memories.
Your decision must follow these rules exactly:

1. INPUTS:
   • Candidate: "{candidate}"
   • Existing Memories (with IDs):
{chr(10).join(f"{i}. {sim['text']}" for i, sim in enumerate(sims, 1))}

2. DECISION LOGIC:
   • You have been given a candidate memory and memories which are semantically similar to it. You need to decide how exactly to integrate this new memory into the user's existing memories.
   • ADD: use only if the candidate is entirely new and does not overlap any existing memory.
   • MERGE: use if the candidate overlaps or extends one or more existing memories.  
     - Format: MERGE: <index>,<index>,...
     - When merging, append candidate to each selected memory, recalculate RFM, and increment its frequency by 1.
   • OVERRIDE: use if the candidate fully replaces one or more existing memories.  
     - Format: OVERRIDE: <index>,<index>,...
     - When overriding, replace memory text with candidate, recalculate RFM, and increment its frequency by 1.

3. REQUIRED OUTPUT:
   - Only output in the format specified above, also shared below , with no additional text or punctuation:
     • add
     • merge: 2  
     • override: 1,3

EXAMPLES:
  • add
  • merge: 1,2
  • override: 3

Respond with your decision now.
"""

    dec = client.models.generate_content(model="gemini-2.5-flash", contents=prompt).text.strip().lower()
    if dec == "add":
        emb = await get_embedding(candidate)
        magnitude = await get_magnitude_for_query(candidate)
        rfm = get_rfm_score(now, frequency=1, magnitude=magnitude)
        await asyncio.to_thread(
            lambda: supabase.table("persona_category")
                          .insert({"user_id":user_id,"memory_text":candidate,"embedding":json.dumps(emb), "magnitude": magnitude, "last_used": now, "frequency": 1, "RFM_score": rfm})
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

                merged = sims[int(idx)-1]["text"] + "\n" + candidate
                emb = await get_embedding(merged)
                magnitude = await get_magnitude_for_query(merged)
                rfm = get_rfm_score(now, frequency= existing_freq+1, magnitude=magnitude)
                await asyncio.to_thread(
                    lambda: supabase.table("persona_category")
                                  .update({"memory_text":merged,"embedding":json.dumps(emb), "magnitude": magnitude, "last_used": now, "frequency": existing_freq +1, "RFM_score": rfm})
                                  .eq("id", id_).execute()
                )
        return f"Merged with {len(idxs)}."
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

                rfm = get_rfm_score(now, frequency= existing_freq+1, magnitude=magnitude)
                
                await asyncio.to_thread(
                    lambda: supabase.table("persona_category")
                                  .update({"memory_text":candidate,"embedding":json.dumps(emb), "magnitude": magnitude, "last_used": now, "frequency": existing_freq +1, "RFM_score": rfm})
                                  .eq("id", id_).execute()
                )
        return f"Overridden {len(idxs)}."
    return "No action taken."

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
