from dotenv import load_dotenv
load_dotenv() 

import os, json, pika
from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv
from google import genai
from .chatbot import get_bot_response_from_memory, get_bot_response_rfm, get_bot_response_combined
from .redis_class import RedisManager
from supabase import create_client
from .serialization import is_valid_memory, serialize_memory, serialize_chat

redis_manager = RedisManager()
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
rabbit_params = pika.URLParameters(os.getenv("RABBITMQ_URL"))
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
app = FastAPI()

class LoginRequest(BaseModel):
    user_id: str

class Message(BaseModel):
    user_id: str
    user_input: str

  

async def publish_to_both_queues(user_id: str, user_input: str, bot_reply: str):
    conn = pika.BlockingConnection(rabbit_params)
    ch = conn.channel()
    # Ensure both queues exist
    memory_queue = f"memory_tasks_user_{user_id}"
    message_queue = f"message_logs_user_{user_id}"

    ch.queue_declare(queue=memory_queue, durable=True)
    ch.queue_declare(queue=message_queue, durable=True)
    task = {
        "user_id": user_id,
        "user_message": user_input,
        "bot_response": bot_reply
    }
    

    # Publish to message_logs
    ch.basic_publish(
        exchange="",
        routing_key=message_queue,
        body=json.dumps(task),
        properties=pika.BasicProperties(delivery_mode=2)
    )
    # Publish to memory_tasks
    ch.basic_publish(
        exchange="",
        routing_key=memory_queue,
        body=json.dumps(task),
        properties=pika.BasicProperties(delivery_mode=2)
    )
    conn.close()


@app.post("/chat-semantic")
async def chat(msg: Message):
    # Generate the bot response
    response = await get_bot_response_from_memory(redis_manager, msg.user_id, msg.user_input)
    await publish_to_both_queues(msg.user_id, msg.user_input, response['response'])
    return response

@app.post("/chat-rfm")
async def chat_rfm_endpoint(msg: Message):
    """Endpoint using only RFM-ranked memories"""
    response = await get_bot_response_rfm(redis_manager, msg.user_id, msg.user_input)
    await publish_to_both_queues(msg.user_id, msg.user_input, response['response'])
    return response


@app.post("/chat-rfm-semantic")
async def chat_combined_endpoint(msg: Message):
    """Endpoint combining RFM and semantic memories"""
   
    response = await get_bot_response_combined(redis_manager, user_id= msg.user_id, user_input= msg.user_input)
    await publish_to_both_queues(msg.user_id, msg.user_input, response['response'])
    return response


@app.post("/login")
async def login(request: LoginRequest):
    user_id = request.user_id
    if not user_id:
        return {"error": "User ID required"}
    # Fetch from Supabase
    memories = supabase.table("persona_category").select("*").eq("user_id", user_id).execute().data
    chats = supabase.table("chat_message_logs").select("*").eq("user_id", user_id).execute().data
    # Load into Redis
    redis_manager.load_user_data(user_id, memories, chats)
    return {"status": "logged_in", "memories_loaded": len(memories), "chats_loaded": len(chats)}


@app.post("/logout")
async def logout(request: LoginRequest):
    user_id = request.user_id
    if not user_id:
        return {"error": "User ID required"}

    # Fetch all data from Redis
    raw_memories = redis_manager.get_user_memories(user_id)
    raw_chats = redis_manager.get_user_chats(user_id)

    # Filter and serialize valid memories
    serialized_memories = []
    for raw in raw_memories:
        if is_valid_memory(raw):
            mem = serialize_memory(raw)
            serialized_memories.append(mem)
    
    #Serializing chats
    serialized_chats = []
    for raw in raw_chats:
        chat = serialize_chat(raw)
        serialized_chats.append(chat)        

     # Batch size (adjust as needed)
    BATCH_SIZE = 100

    # Bulk upsert to Supabase/Postgres in batches
    def batch_upsert(table_name, data):
        for i in range(0, len(data), BATCH_SIZE):
            batch = data[i:i+BATCH_SIZE]
            supabase.table(table_name).upsert(batch).execute()

    if serialized_memories:
        batch_upsert("persona_category", serialized_memories)
    if serialized_chats:
        batch_upsert("chat_message_logs", serialized_chats)
    
    # Clear Redis
    redis_manager.clear_user_data(user_id)
    return {
        "status": "logged_out",
        "memories_synced": len(serialized_memories),
        "chats_synced": len(serialized_chats)
    }


@app.get("/")
async def root():
    """
    Health check endpoint: confirms the chat service is running.
    """
    return {"status": "chat service running"}

