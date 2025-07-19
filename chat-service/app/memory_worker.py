import os
import json
import asyncio
import aio_pika
import requests
import time
from dotenv import load_dotenv

load_dotenv()
RABBIT_URL = os.getenv("RABBITMQ_URL")
RABBITMQ_API_URL = os.getenv("RABBITMQ_API_URL", "http://localhost:15672/api/queues")
RABBITMQ_API_USER = os.getenv("RABBITMQ_API_USER", "guest")
RABBITMQ_API_PASS = os.getenv("RABBITMQ_API_PASS", "guest")
POLL_INTERVAL_SEC = 20  # Check for new queues every 20 seconds

from .memory_functions import generate_candidate_memories, update_user_memory
from .redis_class import RedisManager
redis_manager = RedisManager()

def is_memory_queue(queue_name):
    return queue_name.startswith("memory_tasks_user_")

async def on_memory_task(redis_manager, msg: aio_pika.IncomingMessage):
    async with msg.process():
        try:
            data = json.loads(msg.body)
            user_id = data.get("user_id")
            user_msg = data.get("user_message", "")
            bot_resp = data.get("bot_response", "")

            if not user_id or not user_msg or not bot_resp:
                print(f"[MemoryWorker] Skipping: missing required fields in message: {data}")
                return

            start_time = time.perf_counter()
            print(f"\n[MemoryWorker] Processing for userID: {user_id}")

            try:
                gen_time = time.perf_counter()
                candidates = await generate_candidate_memories(user_id, user_msg, bot_resp)
                gen_time = time.perf_counter() - gen_time
                print(f"[MemoryWorker] Generated {len(candidates)} memories in {gen_time:.3f}s")
            except Exception as e:
                print(f"[MemoryWorker] Error generating candidate memories: {e}")
                candidates = []

            if not candidates:
                print(f"[MemoryWorker] No new candidate memories for user {user_id}.")
            else:
                for i, cand in enumerate(candidates):
                    try:
                        upd_time = time.perf_counter()
                        result = await update_user_memory(redis_manager, cand, user_id, user_msg, bot_resp)
                        upd_time = time.perf_counter() - upd_time
                        print(f"[MemoryWorker] {result} ({upd_time:.3f}s)")
                    except Exception as e:
                        print(f"[MemoryWorker] Error updating memory {i+1}: {e}")

            total = time.perf_counter() - start_time
            print(f"✅ Memory processing for {user_id} finished in {total:.3f}s.")
        except Exception as e:
            print(f"[MemoryWorker] Fatal error: {e}")

async def monitor_and_consume_queues():
    print("Connecting to RabbitMQ...")
    conn = await aio_pika.connect_robust(RABBIT_URL)
    channel = await conn.channel()
    await channel.set_qos(prefetch_count=3)

    consumers = {}
    queue_timeout_ms = 10 * 60 * 1000  # 10 minutes

    async def add_consumer(queue_name):
        if queue_name in consumers:
            return
        queue = await channel.declare_queue(queue_name, durable=True)
        tag = await queue.consume(lambda msg: on_memory_task(redis_manager, msg))
        consumers[queue_name] = tag
        print(f"[MemoryWorker] Now consuming: {queue_name}")

    while True:
        try:
            resp = requests.get(
                RABBITMQ_API_URL,
                auth=(RABBITMQ_API_USER, RABBITMQ_API_PASS),
                timeout=5
            )
            resp.raise_for_status()
            all_queues = [q['name'] for q in resp.json()]
            memory_queues = [q for q in all_queues if is_memory_queue(q)]

            for q in memory_queues:
                await add_consumer(q)

            # Remove consumers for queues that have disappeared
            active = set(memory_queues)
            stale = [q for q in list(consumers.keys()) if q not in active]
            for q in stale:
                del consumers[q]
                print(f"[MemoryWorker] Pruned consumer for expired queue: {q}")

            print(f"[MemoryWorker] Listening to {len(consumers)} memory task queues...")
        except Exception as e:
            print(f"[MemoryWorker] Queue discovery error: {e}")
        await asyncio.sleep(POLL_INTERVAL_SEC)

if __name__ == "__main__":
    asyncio.run(monitor_and_consume_queues())
