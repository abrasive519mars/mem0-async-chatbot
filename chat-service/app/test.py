import os
import json
import asyncio
import aio_pika
import requests
from dotenv import load_dotenv




from .memory_functions import log_message
from .redis_class import RedisManager

import requests

from dotenv import load_dotenv

load_dotenv()

RABBIT_URL = os.getenv("RABBITMQ_URL")
RABBITMQ_API_URL = os.getenv("RABBITMQ_API_URL")
RABBITMQ_API_USER = os.getenv("RABBITMQ_API_USER", "guest")
RABBITMQ_API_PASS = os.getenv("RABBITMQ_API_PASS", "guest")
POLL_INTERVAL_SEC = 20 # Poll RabbitMQ API every 20 seconds

print(RABBITMQ_API_URL, RABBITMQ_API_PASS, RABBITMQ_API_USER, RABBIT_URL)