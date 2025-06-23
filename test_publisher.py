import pika
import json

# Connect to RabbitMQ
connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()

# Declare the queue (creates if doesn't exist)
channel.queue_declare(queue='memory_tasks', durable=True)

# Test message
test_message = {
    "user_id": "test_user",
    "user_message": "Hello RabbitMQ!",
    "bot_response": "Testing message queue"
}

# Publish message
channel.basic_publish(
    exchange='',
    routing_key='memory_tasks',
    body=json.dumps(test_message),
    properties=pika.BasicProperties(delivery_mode=2)  # Make message persistent
)

print("✅ Test message sent to RabbitMQ")
connection.close()
