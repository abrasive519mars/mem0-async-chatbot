from dotenv import load_dotenv
load_dotenv() 

import os, json, pika
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from google import genai
from .chatbot import get_bot_response_from_memory

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
rabbit_params = pika.URLParameters(os.getenv("RABBITMQ_URL"))

app = FastAPI()

class Message(BaseModel):
    user_id: str
    user_input: str
   

@app.post("/chat")
async def chat(msg: Message):
    # Generate the bot response
    response = await get_bot_response_from_memory(msg.user_id, msg.user_input)
    reply_text = response

    # Publish memory task
    conn = pika.BlockingConnection(rabbit_params)
    ch   = conn.channel()
    ch.queue_declare(queue="memory_tasks", durable=True)
    task = {
        "user_id":      msg.user_id,
        "user_message": msg.user_input,
        "bot_response": reply_text
    }
    ch.basic_publish(
        exchange="",
        routing_key="memory_tasks",
        body=json.dumps(task),
        properties=pika.BasicProperties(delivery_mode=2)
    )
    conn.close()

    return {"reply": reply_text}

@app.get("/")
async def root():
    """
    Health check endpoint: confirms the chat service is running.
    """
    return {"status": "chat service running"}

'''''''''''''''
@app.post("/chat_stream")
async def chat_stream(msg: Message):
    stream = await client.aio.models.generate_content_stream(
        model="gemini-2.5-flash",
        contents=msg.user_input
    )

    buffer = ""
    async def streamer():
        nonlocal buffer
        async for chunk in stream:
            buffer += chunk.text or ""
            yield chunk.text or ""

    # Publish after streaming completes
    import asyncio
    async def publish():
        await stream.aclose()
        conn = pika.BlockingConnection(rabbit_params)
        ch   = conn.channel()
        ch.queue_declare(queue="memory_tasks", durable=True)
        task = {
            "user_id":      msg.user_id,
            "user_message": msg.user_input,
            "bot_response": buffer
        }
        ch.basic_publish(
            exchange="",
            routing_key="memory_tasks",
            body=json.dumps(task),
            properties=pika.BasicProperties(delivery_mode=2)
        )
        conn.close()

    asyncio.create_task(publish())
    return StreamingResponse(streamer(), media_type="text/event-stream")
    '''