import requests
import time
import os
from dotenv import load_dotenv

load_dotenv()

RABBITMQ_API_URL = os.getenv("RABBITMQ_API_URL", "http://localhost:15672/api/queues")
RABBITMQ_API_USER = os.getenv("RABBITMQ_API_USER", "guest")
RABBITMQ_API_PASS = os.getenv("RABBITMQ_API_PASS", "guest")
CLEANUP_INTERVAL_SEC = int(os.getenv("CLEANUP_INTERVAL_SEC", "60"))

auth = (RABBITMQ_API_USER, RABBITMQ_API_PASS)

def cleanup_empty_queues():
    try:
        resp = requests.get(RABBITMQ_API_URL, auth=auth, timeout=10)
        resp.raise_for_status()
        for queue in resp.json():
            name = queue['name']
            if name.startswith("message_logs_user_") or name.startswith("memory_tasks_user_"):
                if queue['messages'] == 0:
                    vhost = queue['vhost'].replace('/', '%2F')
                    del_url = f"{RABBITMQ_API_URL.rsplit('/api/queues', 1)[0]}/api/queues/{vhost}/{name}"
                    r = requests.delete(del_url, auth=auth, timeout=10)
                    if r.status_code == 204:
                        print(f"Deleted empty queue: {name}")
        print("Queue Cleanup completed.")
    except Exception as e:
        print(f"Error during cleanup: {e}")

if __name__ == "__main__":
    print("Starting periodic RabbitMQ cleanup...")
    while True:
        cleanup_empty_queues()
        time.sleep(CLEANUP_INTERVAL_SEC)

