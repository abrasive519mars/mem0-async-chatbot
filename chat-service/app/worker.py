import os, json, asyncio
from dotenv import load_dotenv
import aio_pika
from .memory_functions import (
    generate_candidate_memories,
    update_user_memory,
    log_message
)

load_dotenv()
RABBIT_URL = (
    f"amqp://{os.getenv('RABBITMQ_USER')}:"
    f"{os.getenv('RABBITMQ_PASSWORD')}@"
    f"{os.getenv('RABBITMQ_HOST')}:{os.getenv('RABBITMQ_PORT')}/"
)

async def on_message(msg: aio_pika.IncomingMessage):
    async with msg.process():
        data = json.loads(msg.body)
        user_id = data["user_id"]
        user_msg = data["user_message"]
        bot_resp = data["bot_response"]

        # Execute memory pipeline
        candidates = await generate_candidate_memories(user_id, user_msg, bot_resp)
        for cand in candidates:
            result = await update_user_memory(cand, user_id)
            print(f"🛠️ {result}")
        await log_message(user_id, user_msg, bot_resp)
        print(f"✅ Processed task for {user_id}")

async def main():
    conn = await aio_pika.connect_robust(RABBIT_URL)
    channel = await conn.channel()
    await channel.set_qos(prefetch_count=1)
    queue = await channel.declare_queue("memory_tasks", durable=True)
    await queue.consume(on_message)
    print("🔄 Memory worker started. Waiting for messages...")
    await asyncio.Future()  # Keep running

if __name__ == "__main__":
    asyncio.run(main())
