from dotenv import load_dotenv
load_dotenv() 

import os, json, pika
from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv
from google import genai
from .chatbot import get_bot_response_from_memory, get_bot_response_rfm, get_bot_response_combined

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
rabbit_params = pika.URLParameters(os.getenv("RABBITMQ_URL"))

app = FastAPI()

class Message(BaseModel):
    user_id: str
    user_input: str

def publish_memory_task(user_id: str, user_input: str, bot_reply: str):
    conn = pika.BlockingConnection(rabbit_params)
    ch = conn.channel()
    ch.queue_declare(queue="memory_tasks", durable=True)
    task = {
        "user_id": user_id,
        "user_message": user_input,
        "bot_response": bot_reply
    }
    ch.basic_publish(
        exchange="",
        routing_key="memory_tasks",
        body=json.dumps(task),
        properties=pika.BasicProperties(delivery_mode=2)
    )
    conn.close()

@app.post("/chat-semantic")
async def chat(msg: Message):
    # Generate the bot response
    response = await get_bot_response_from_memory(msg.user_id, msg.user_input)
    reply_text = response
    publish_memory_task(msg.user_id, msg.user_input, reply_text)
    return {"reply": reply_text}

@app.post("/chat-rfm")
async def chat_rfm_endpoint(msg: Message):
    """Endpoint using only RFM-ranked memories"""
    response = await get_bot_response_rfm(msg.user_id, msg.user_input)
    reply_text = response
    publish_memory_task(msg.user_id, msg.user_input, reply_text)
    return {"reply": reply_text}

@app.post("/chat-rfm-semantic")
async def chat_combined_endpoint(msg: Message):
    """Endpoint combining RFM and semantic memories"""
   
    response = await get_bot_response_combined(user_id= msg.user_id, user_input= msg.user_input)
    reply_text = response
    publish_memory_task(msg.user_id, msg.user_input, reply_text)
    return {"reply": reply_text}


@app.get("/")
async def root():
    """
    Health check endpoint: confirms the chat service is running.
    """
    return {"status": "chat service running"}

