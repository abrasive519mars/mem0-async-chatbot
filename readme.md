Context-Aware Chatbot Service
Welcome to the Chatbot Service repository!
This project is an LLM-powered, context-sensitive chatbot stack that integrates semantic memory, RFM-based relevance, Redis caching, FastAPI endpoints, Supabase/Postgres for persistence, and RabbitMQ-powered asynchronous message/memory logging.

🏗️ Architecture Overview
Below is a visual summary of the system, illustrating the login/logout flows, chat API, Redis caching, semantic/RFM retrieval, and asynchronous processing backbone.

[image:2]

📦 Features
Conversational FastAPI server: RFM and semantic memory-aware endpoints for engaging dialog.

Supabase/Postgres integration: Persist chat logs and memories.

Redis caching layer: Ultra-fast session/stateful memory for chat state and context.

RabbitMQ queues: Decoupled, scalable message and memory background workers.

Automatic user memory management: Extract, consolidate, merge, or override user memories using LLMs.

Periodic queue/Redis cleanup: Efficient resource management.

Pluggable embedding & LLM: Uses Google's Gemini and Embeddings API via genai.

Environment-configurable: All sensitive tokens/keys in .env.

🛠️ Getting Started
1. Environment Setup
Clone this repository and enter the root.

Ensure you have:

Python 3.10+ (recommended)

Redis server

Supabase/Postgres instance

RabbitMQ server

Install Python dependencies:

bash
pip install -r requirements.txt
Set up .env:
Fill in your API and database/RabbitMQ credentials:

text
#Google API
GOOGLE_API_KEY=AIzaSyDzuQhoyZfAbWsyyqIv8HF0G0R_gA5f3F0

#Database
SUPABASE_URL=
SUPABASE_KEY=

#RabbitMQ URL 
RABBITMQ_API_URL=http://34.131.220.37:15672/api/queues 
RABBITMQ_URL=amqp://myadmin:strongpassword@34.131.220.37:5672/
RABBITMQ_API_USER=myadmin
RABBITMQ_API_PASS=strongpassword


REDIS_HOST=34.131.107.77
REDIS_PORT=6379

# Application settings
ENV=development
LOG_LEVEL=debug

2. Run the Services
Start the FastAPI server:

bash
uvicorn chat-service.app.main:app --reload --port 8000
Start the message worker:

bash
python -m app.message_worker
Start the memory worker:

bash
python -m app.memory_worker
Start the queue cleanup utility:

bash
python -m app.queue_cleanup
All services must share access to your .env variables.

🚦 API Usage
Endpoints
1. POST /login
Purpose: Loads user memories & chats from Supabase into Redis on login.

Request: { "user_id": string }

Response: Number of records loaded.

2. POST /logout
Purpose: Syncs session memories/chats from Redis back to Supabase (batched), clears Redis user data.

Request: { "user_id": string }

Response: Number of records synced.

3. POST /chat-semantic
Purpose: LLM answers with semantic memory retrieval.

Body: { "user_id": string, "user_input": string }

Response: {response, timing metrics, retrieved memory blocks}

4. POST /chat-rfm
Purpose: LLM answers using only RFM-ranked (Recency, Frequency, Magnitude) important memories.

Body: { "user_id": string, "user_input": string }

5. POST /chat-rfm-semantic
Purpose: LLM answers with both semantic + RFM hybrid memory context.

6. GET /
Health check.

🧠 Memory System Design
Semantic Retrieval:
Vector embeddings (768D) via Google Embeddings API.
Top similar memories fetched using k-NN query in Redis.

RFM Retrieval:
Memories are scored by recency, frequency, and magnitude (importance via LLM).

Combined Retrieval:
Endpoints can combine semantically relevant and important (RFM) memories for most context-rich answers.

Updating Memories:

On each conversation turn, new user memories are extracted (if found) by an LLM and processed:

If duplicate: override

If overlapping: merge with existing

If new: add to Redis

Else: skip

⛓️ Background Workers
Message Worker:
Consumes message_logs_user_{user_id} queue. Logs each user-bot exchange into Redis.

Memory Worker:
Consumes memory_tasks_user_{user_id} queue.
Extracts, evaluates, and updates user memories accordingly.

Queue Auto-Cleanup:
A periodic cleaner deletes empty message/memory queues from RabbitMQ (configurable period).

🗄️ Persistence & Caching
Supabase/Postgres:
These two tables are required for memory store.
persona_category (user memories)
create table public.chat_message_logs (
  id uuid not null default gen_random_uuid (),
  user_id text not null,
  user_message text null,
  bot_response text null,
  timestamp timestamp with time zone null default now(),
  constraint chat_message_logs_pkey primary key (id)
) TABLESPACE pg_default;

chat_message_logs (chat logs)
create table public.persona_category (
  id uuid not null default gen_random_uuid (),
  user_id text not null,
  memory_text text null,
  embedding public.vector null,
  created_at timestamp with time zone null default now(),
  last_used timestamp with time zone null default now(),
  frequency integer null default 1,
  magnitude real null,
  rfm_score real null,
  constraint persona_category_pkey primary key (id)
) TABLESPACE pg_default;

create index IF not exists persona_category_embedding_hnsw_idx on public.persona_category using hnsw (embedding vector_cosine_ops)
with
  (m = '16', ef_construction = '64') TABLESPACE pg_default;

Bulk upsert on logout for durability.

Redis:
redis-stack should be installeld (Already setup on VM) with indexes


FT.CREATE memories_idx ON HASH PREFIX 1 memories: SCHEMA user_id TAG SEPARATOR , memory_text TEXT WEIGHT 1 embedding VECTOR HNSW 10 TYPE FLOAT32 DIM 768 DISTANCE_METRIC COSINE M 16 EF_CONSTRUCTION 200 rfm_score NUMERIC magnitude NUMERIC frequency NUMERIC created_at TEXT WEIGHT 1 last_used TEXT WEIGHT 1

FT.CREATE chats_idx ON HASH PREFIX 1 chat: SCHEMA user_message TEXT WEIGHT 1 bot_response TEXT WEIGHT 1 user_id TAG SEPARATOR , timestamp TEXT WEIGHT 1

Stores session memories & chat logs for low-latency retrieval during conversation.

RabbitMQ:

Used for asynchronous message and memory logging/processing for scalability.
(Already setup in VM.)



✨ Modular Code Structure
chatbot.py - Main LLM and context management

main.py - FastAPI endpoints

memory_functions.py - Embedding, memory logic, summarization, updating/merging memories

redis_class.py - Redis connection and utility layer

message_worker.py & memory_worker.py - RabbitMQ workers

queue_cleanup.py - Periodic queue cleanup utility

RFM_functions.py - Recency, frequency, magnitude, and scorer functions

serialization.py - Safe upsert/validation for Supabase rows

👤 User Memory Extraction & Management
LLM analyzes each chat turn for new, significant facts about the user.

Redundant, trivial, or overly generic facts are filtered.

All updates are performed asynchronously in Redis until logout.

📝 Example .env File
text
GOOGLE_API_KEY=your_google_genai_api_key
SUPABASE_URL=your-supabase-project-url
SUPABASE_KEY=your-supabase-service-role-key
RABBITMQ_URL=amqp://guest:guest@rabbitmq-host:5672/
RABBITMQ_API_URL=http://rabbitmq-host:15672/api/queues
RABBITMQ_API_USER=guest
RABBITMQ_API_PASS=guest
CLEANUP_INTERVAL_SEC=60
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
⚠️ Notes
Never commit actual API keys, database URIs, or production credentials.

You are responsible for providing your own Google GenAI, Supabase, and RabbitMQ configuration.

Make sure Redis, RabbitMQ, and Supabase are running and accessible before starting the app and background workers.

🤝 Contributing
PRs and issues welcome—custom logic for memory scoring, new retrieval strategies, or improved serialization are all possible extension points!