import os
import json
import asyncio
import aio_pika
import requests
from dotenv import load_dotenv

load_dotenv()

RABBIT_URL = os.getenv("RABBITMQ_URL")
RABBITMQ_API_URL = os.getenv("RABBITMQ_API_URL", "http://localhost:15672/api/queues")
RABBITMQ_API_USER = os.getenv("RABBITMQ_API_USER", "guest")
RABBITMQ_API_PASS = os.getenv("RABBITMQ_API_PASS", "guest")
POLL_INTERVAL_SEC = 20 # Poll RabbitMQ API every 20 seconds

from .memory_functions import log_message
from .redis_class import RedisManager
redis_manager = RedisManager()

def is_message_log_queue(queue_name):
    return queue_name.startswith("message_logs_user_")

async def on_message_log(redis_manager, msg: aio_pika.IncomingMessage):
    async with msg.process():
        try:
            data = json.loads(msg.body)
            await log_message(redis_manager, data["user_id"], data["user_message"], data["bot_response"])
            print(f"[MessageWorker] Logged message for user {data['user_id']}")
        except Exception as e:
            print(f"[MessageWorker] Error: {e}")

async def monitor_and_consume_queues():
    print("Connecting to RabbitMQ...")
    conn = await aio_pika.connect_robust(RABBIT_URL)
    channel = await conn.channel()
    await channel.set_qos(prefetch_count=10)

    consumers = {}
    queue_timeout_ms = 10 * 60 * 1000

    async def add_consumer(queue_name):
        if queue_name in consumers:
            return
        queue = await channel.declare_queue(queue_name, durable=True)
        tag = await queue.consume(lambda msg: on_message_log(redis_manager, msg))
        consumers[queue_name] = tag
        print(f"[MessageWorker] Now consuming: {queue_name}")

    while True:
        try:
            resp = requests.get(
                RABBITMQ_API_URL,
                auth=(RABBITMQ_API_USER, RABBITMQ_API_PASS),
                timeout=5
            )
            resp.raise_for_status()
            all_queues = [q['name'] for q in resp.json()]
            log_queues = [q for q in all_queues if is_message_log_queue(q)]
            # Attach consumer for any new queue
            for q in log_queues:
                await add_consumer(q)
            # Remove consumers for queues that have disappeared, so that when they are added back they can be called again.
            active = set(log_queues)
            stale = [q for q in list(consumers.keys()) if q not in active]
            for q in stale:
                # No manual cancel needed; just remove from dict
                del consumers[q]
            print(f"[MessageWorker] Listening to {len(consumers)} message log queues...")
        except Exception as e:
            print(f"[MessageWorker] Queue discovery error: {e}")
        await asyncio.sleep(POLL_INTERVAL_SEC)

if __name__ == "__main__":
    asyncio.run(monitor_and_consume_queues())
