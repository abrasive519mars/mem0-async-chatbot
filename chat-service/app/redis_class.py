import redis
import numpy as np
from datetime import datetime, timezone
import json
from dotenv import load_dotenv
import os

load_dotenv()
#docker exec -it redis-stack redis-cli

class RedisManager:
    def __init__(self, host=None, port=None, db=0):
        host = host or os.environ.get('REDIS_HOST', 'localhost')
        port = port or int(os.environ.get('REDIS_PORT', 6379))
        db = db or int(os.environ.get('REDIS_DB', 0))
        self.client = redis.Redis(host=host, port=port, db=db)
        self.client = redis.Redis(host=host, port=port, db=db)

    def store_memory(self, user_id, mem_id, memory_dict):
        key = f"memories:{user_id}:{mem_id}"
        mapping = {}
        for k, v in memory_dict.items():
            if k == 'embedding':
                # If it's already bytes, use as-is; if it's a string, convert from JSON
                if isinstance(v, bytes):
                    mapping[k] = v
                elif isinstance(v,list):
                    mapping[k] = np.array(v, dtype=np.float32).tobytes()
                else:
                    mapping[k] = np.array(json.loads(v), dtype=np.float32).tobytes()
            else:
                mapping[k] = str(v) if not isinstance(v, str) else v
        self.client.hset(key, mapping=mapping)

    def store_chat(self, user_id, chat_id, chat_dict):
        key = f"chat:{user_id}:{chat_id}"
        self.client.hset(key, mapping=chat_dict)

    def load_user_data(self, user_id, memories, chats):
        for mem in memories:
            mem_id = mem['id']
            self.store_memory(user_id, mem_id, mem)
        for chat in chats:
            chat_id = chat['id']
            self.store_chat(user_id, chat_id, chat)
    
    def get_user_memories(self, user_id):
        pattern = f"memories:{user_id}:*"
        keys = self.client.keys(pattern)
        memories = []
        for key in keys:
            mem = self.client.hgetall(key)
            decoded_mem = {}
            for k, v in mem.items():
                k = k.decode() if isinstance(k, bytes) else k
                if k == "embedding":
                    decoded_mem[k] = np.frombuffer(v, dtype=np.float32)
                else:
                    decoded_mem[k] = v.decode() if isinstance(v, bytes) else v
            decoded_mem["__redis_key__"] = key.decode() if isinstance(key, bytes) else key
            memories.append(decoded_mem)
        return memories

    def get_user_chats(self, user_id):
        pattern = f"chat:{user_id}:*"
        keys = self.client.keys(pattern)
        chats = []
        for key in keys:
            chat = self.client.hgetall(key)
            decoded_chat = {}
            for k, v in chat.items():
                k = k.decode() if isinstance(k, bytes) else k
                decoded_chat[k] = v.decode() if isinstance(v, bytes) else v
            decoded_chat["__redis_key__"] = key.decode() if isinstance(key, bytes) else key
            chats.append(decoded_chat)
        return chats
    
    def clear_user_data(self, user_id):
        # Remove all memory and chat keys for this user
        mem_keys = self.client.keys(f"memories:{user_id}:*")
        chat_keys = self.client.keys(f"chat:{user_id}:*")
        total_keys = mem_keys + chat_keys 
        decoded_keys = [key.decode('utf-8') for key in total_keys]
        if decoded_keys:
          self.client.delete(*decoded_keys)
        return len(total_keys) 
          
            

    