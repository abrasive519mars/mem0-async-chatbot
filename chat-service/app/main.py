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

def publish_to_both_queues(user_id: str, user_input: str, bot_reply: str):
    conn = pika.BlockingConnection(rabbit_params)
    ch = conn.channel()
    # Ensure both queues exist
    ch.queue_declare(queue="memory_tasks", durable=True)
    ch.queue_declare(queue="message_logs", durable=True)
    task = {
        "user_id": user_id,
        "user_message": user_input,
        "bot_response": bot_reply
    }
    # Publish to memory_tasks
    ch.basic_publish(
        exchange="",
        routing_key="memory_tasks",
        body=json.dumps(task),
        properties=pika.BasicProperties(delivery_mode=2)
    )
    # Publish to message_logs
    ch.basic_publish(
        exchange="",
        routing_key="message_logs",
        body=json.dumps(task),
        properties=pika.BasicProperties(delivery_mode=2)
    )
    conn.close()


@app.post("/chat-semantic")
async def chat(msg: Message):
    # Generate the bot response
    response = await get_bot_response_from_memory(msg.user_id, msg.user_input)
    publish_to_both_queues(msg.user_id, msg.user_input, response['response'])
    return response

@app.post("/chat-rfm")
async def chat_rfm_endpoint(msg: Message):
    """Endpoint using only RFM-ranked memories"""
    response = await get_bot_response_rfm(msg.user_id, msg.user_input)
    publish_to_both_queues(msg.user_id, msg.user_input, response['response'])
    return response


@app.post("/chat-rfm-semantic")
async def chat_combined_endpoint(msg: Message):
    """Endpoint combining RFM and semantic memories"""
   
    response = await get_bot_response_combined(user_id= msg.user_id, user_input= msg.user_input)
    publish_to_both_queues(msg.user_id, msg.user_input, response['response'])
    return response


@app.get("/")
async def root():
    """
    Health check endpoint: confirms the chat service is running.
    """
    return {"status": "chat service running"}

