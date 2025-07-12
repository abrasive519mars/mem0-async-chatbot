# worker.py
import os
import json
import asyncio
import time
from dotenv import load_dotenv
import aio_pika

load_dotenv()
RABBIT_URL = os.getenv("RABBITMQ_URL")

# Import your memory functions at the top as before
from .memory_functions import (
    generate_candidate_memories,
    update_user_memory,
    log_message
)

# --- Message Logging Worker ---
async def on_message_log(msg: aio_pika.IncomingMessage):
    async with msg.process():
        data = json.loads(msg.body)
        user_id = data["user_id"]
        user_msg = data["user_message"]
        bot_resp = data["bot_response"]

        start_time = time.perf_counter()
        await log_message(user_id, user_msg, bot_resp)
        elapsed = time.perf_counter() - start_time
        print(f"[MessageLog] Logged message for user {user_id} in {elapsed:.3f}s")

# --- Memory Processing Worker ---
async def on_memory_task(msg: aio_pika.IncomingMessage):
    async with msg.process():
        data = json.loads(msg.body)
        user_id = data["user_id"]
        user_msg = data["user_message"]
        bot_resp = data["bot_response"]

        start_time = time.perf_counter()
        print(f"\n*-------------------------------*\n[MemoryWorker] Processing for user: {user_id}")
        print(f"User: {user_msg[:80]}....")
        print(f"Bot: {bot_resp[:80]}....")
        # Generate and process candidate memories
        gen_time = time.perf_counter()
        candidates = await generate_candidate_memories(user_id, user_msg, bot_resp)
        gen_time = time.perf_counter() - gen_time
        print(f"[MemoryWorker] Generated {len(candidates)} memories in {gen_time:.3f}s")
        for i, cand in enumerate(candidates):
            print(f"  Processing memory {i} - {cand}")
            upd_time = time.perf_counter()
            result = await update_user_memory(cand, user_id, user_msg, bot_resp)
            upd_time = time.perf_counter() - upd_time
            print(f"🛠️ {result} in {upd_time:.3f}s")
        total = time.perf_counter() - start_time
        print(f"✅ Memory processing for {user_id} finished in {total:.3f}s.")

# --- Main: Run Both Consumers ---
async def main():
    while True:
        try:
            conn = await aio_pika.connect_robust(RABBIT_URL)
            print("Connected to RabbitMQ!")
            channel = await conn.channel()
            await channel.set_qos(prefetch_count=1)

            # Declare both queues
            message_log_queue = await channel.declare_queue("message_logs", durable=True)
            memory_task_queue = await channel.declare_queue("memory_tasks", durable=True)

            # Start both consumers
            await message_log_queue.consume(on_message_log)
            await memory_task_queue.consume(on_memory_task)

            print("🔄 Workers started. Waiting for messages...")
            await asyncio.Future()  # Keep running
        except Exception as e:
            print(f"Failed to connect to RabbitMQ or set up queues: {e}")
            print("Retrying in 3 seconds...")
            await asyncio.sleep(3)

if __name__ == "__main__":
    asyncio.run(main())
