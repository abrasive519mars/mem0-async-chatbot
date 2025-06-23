import pika
import json

def process_message(ch, method, properties, body):
    try:
        message = json.loads(body)
        print(f"📨 Received message: {message}")
        
        # Acknowledge the message
        ch.basic_ack(delivery_tag=method.delivery_tag)
        print("✅ Message processed successfully")
        
    except Exception as e:
        print(f"❌ Error processing message: {e}")

# Connect to RabbitMQ
connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()

# Declare the queue
channel.queue_declare(queue='memory_tasks', durable=True)

# Set up consumer
channel.basic_qos(prefetch_count=1)
channel.basic_consume(queue='memory_tasks', on_message_callback=process_message)

print("🔄 Waiting for messages. To exit press CTRL+C")
try:
    channel.start_consuming()
except KeyboardInterrupt:
    print("\n🛑 Stopping consumer...")
    channel.stop_consuming()
    connection.close()
