import numpy as np
import re

REQUIRED_MEMORY_FIELDS = [
    "id", "user_id", "memory_text", "embedding", "magnitude",
    "last_used", "frequency", "rfm_score", "created_at"
]

EMB_DIM = 768

def serialize_memory(mem):
    # Converts a memory dict for safe Supabase upsert
    serialized = {}
    for k, v in mem.items():
        if k == "embedding":
            if isinstance(v, np.ndarray):
                serialized[k] = v.tolist()
            else:
                serialized[k] = v  # Already a list or None
        elif k != "__redis_key__":
            serialized[k] = v
    return serialized

def serialize_chat(chat):
    # Converts a chat dict for safe Supabase upsert
    return {k: v for k, v in chat.items() if k != "__redis_key__"}

import numpy as np
 

def is_valid_memory(mem):
    # Check for presence of all required fields
    for field in REQUIRED_MEMORY_FIELDS:
        if field not in mem or mem[field] is None or (isinstance(mem[field], str) and not mem[field].strip()):
            return False
    # Check embedding shape
    emb = mem["embedding"]
    if not isinstance(emb, np.ndarray) or emb.size != EMB_DIM:
        return False
    # Check numeric fields
    try:
        float(mem["magnitude"])
        int(mem["frequency"])
    except (TypeError, ValueError):
        return False
    return True
