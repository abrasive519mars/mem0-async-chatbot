# 🤖 Context-Aware Chatbot Service

Welcome to the **Chatbot Service** repository!

This project is an **LLM-powered, context-sensitive chatbot stack** that integrates:

- ✨ Semantic memory  
- 🧠 RFM-based relevance scoring  
- ⚡ Redis caching  
- 🚀 FastAPI endpoints  
- 📦 Supabase/Postgres for persistence  
- 🐇 RabbitMQ-powered asynchronous message/memory logging  

---

## 🏗️ Architecture Overview

Below is a visual summary of the system, illustrating:

- Login/logout flows  
- Chat APIs  
- Redis caching  
- Semantic & RFM retrieval  
- Asynchronous background processing  

> _[Insert architecture image here]_  

---

## 📦 Features

- **Conversational FastAPI server**: RFM and semantic memory-aware endpoints for engaging dialog  
- **Supabase/Postgres integration**: Persist chat logs and memories  
- **Redis caching layer**: Ultra-fast session/stateful memory for chat state and context  
- **RabbitMQ queues**: Decoupled, scalable message and memory background workers  
- **Automatic memory management**: Extract, consolidate, merge, or override memories using LLMs  
- **Periodic queue/Redis cleanup**: Efficient resource management  
- **Pluggable embedding & LLM support**: Uses Google’s Gemini & Embeddings API  
- **Environment-configurable**: All tokens/keys in `.env`  

---

## 🛠️ Getting Started

### 1. Environment Setup

Clone the repo and enter the root:

```bash
git clone <repo_url>
cd chat-service
cd app
```

**Ensure you have:**

- Python 3.10+  
- Redis server  
- Supabase/Postgres instance  
- RabbitMQ server  

**Install dependencies:**

```bash
pip install -r requirements.txt
```

Set up `.env`:  
Create a `.env` file in the root with:

```bash
# Google API
GOOGLE_API_KEY=your_google_genai_api_key

# Supabase
SUPABASE_URL=your_supabase_project_url
SUPABASE_KEY=your_supabase_service_role_key

# RabbitMQ
RABBITMQ_URL=amqp://myadmin:strongpassword@34.131.220.37:5672/
RABBITMQ_API_URL=http://34.131.220.37:15672/api/queues
RABBITMQ_API_USER=myadmin
RABBITMQ_API_PASS=strongpassword

# Redis
REDIS_HOST=34.131.107.77
REDIS_PORT=6379

# App Settings
ENV=development
LOG_LEVEL=debug
```

---

### 2. Run the Services

Start FastAPI server:

```bash
uvicorn chat-service.app.main:app --reload --port 8000
```

Start message worker:

```bash
python -m app.message_worker
```

Start memory worker:

```bash
python -m app.memory_worker
```

Start periodic queue cleanup:

```bash
python -m app.queue_cleanup
```

> 💡 Make sure all services share access to your `.env` variables.

---

## 🚦 API Usage

### Endpoints

#### `POST /login`  
**Purpose**: Loads user memories & chats from Supabase into Redis.  
**Body**:
```json
{ "user_id": "string" }
```

#### `POST /logout`  
**Purpose**: Syncs session memories/chats from Redis to Supabase.  
**Body**:
```json
{ "user_id": "string" }
```

#### `POST /chat-semantic`  
**Purpose**: LLM answers with semantic memory retrieval.  
**Body**:
```json
{ "user_id": "string", "user_input": "string" }
```

#### `POST /chat-rfm`  
**Purpose**: LLM answers using only RFM-ranked important memories.

#### `POST /chat-rfm-semantic`  
**Purpose**: Combines semantic + RFM memory context for the most relevant responses.

#### `GET /`  
**Purpose**: Health check.

---

## 🧠 Memory System Design

### Semantic Retrieval
- Vector embeddings (768D) via Google Embeddings API  
- Top-k similar memories fetched using Redis HNSW  

### RFM Retrieval
Scores based on:
- **Recency**  
- **Frequency**  
- **Magnitude** (importance, LLM evaluated)  

### Combined Retrieval
- Use both semantic similarity & RFM scoring for highly contextual answers

### Memory Update Logic
Each chat turn may extract new memory facts:
- If duplicate: override  
- If overlapping: merge  
- If new: add to Redis  
- Else: skip  

---

## ⛓️ Background Workers

### Message Worker
- **Queue**: `message_logs_user_{user_id}`  
- **Function**: Logs user-bot exchanges into Redis  

### Memory Worker
- **Queue**: `memory_tasks_user_{user_id}`  
- **Function**: Extracts, evaluates, and updates user memories  

### Queue Cleanup
- Periodic cleanup of empty RabbitMQ queues  
- **Interval**: Configurable via `.env` (`CLEANUP_INTERVAL_SEC`)  

---

## 🗄️ Persistence & Caching

### Supabase/Postgres

Two required tables:

```sql
-- chat_message_logs
create table public.chat_message_logs (
  id uuid primary key default gen_random_uuid (),
  user_id text not null,
  user_message text,
  bot_response text,
  timestamp timestamp with time zone default now()
);
```

```sql
-- persona_category
create table public.persona_category (
  id uuid primary key default gen_random_uuid (),
  user_id text not null,
  memory_text text,
  embedding public.vector,
  created_at timestamp with time zone default now(),
  last_used timestamp with time zone default now(),
  frequency integer default 1,
  magnitude real,
  rfm_score real
);
```

HNSW Index for vector search:

```sql
create index if not exists persona_category_embedding_hnsw_idx 
on public.persona_category using hnsw (embedding vector_cosine_ops)
with (m = '16', ef_construction = '64');
```

> Bulk upsert on logout for durability.

---

### Redis

Ensure redis-stack is installed.

#### Memory Index:
```bash
FT.CREATE memories_idx ON HASH PREFIX 1 memories: SCHEMA \
user_id TAG SEPARATOR , \
memory_text TEXT WEIGHT 1 \
embedding VECTOR HNSW 10 TYPE FLOAT32 DIM 768 DISTANCE_METRIC COSINE M 16 EF_CONSTRUCTION 200 \
rfm_score NUMERIC magnitude NUMERIC frequency NUMERIC \
created_at TEXT WEIGHT 1 last_used TEXT WEIGHT 1
```

#### Chat Index:
```bash
FT.CREATE chats_idx ON HASH PREFIX 1 chat: SCHEMA \
user_message TEXT WEIGHT 1 \
bot_response TEXT WEIGHT 1 \
user_id TAG SEPARATOR , \
timestamp TEXT WEIGHT 1
```

---

### RabbitMQ

- Used for asynchronous message and memory logging & processing  
- Already configured on the VM

---

## ✨ Modular Code Structure

| File                         | Purpose                                           |
|------------------------------|---------------------------------------------------|
| `chatbot.py`                 | Main LLM and context management                  |
| `main.py`                    | FastAPI endpoint definitions                     |
| `memory_functions.py`        | Embedding, summarization, and memory logic      |
| `redis_class.py`             | Redis utility and connection layer              |
| `message_worker.py`          | RabbitMQ message logger                         |
| `memory_worker.py`           | RabbitMQ memory updater                         |
| `queue_cleanup.py`           | Periodic cleanup utility                        |
| `RFM_functions.py`           | RFM scoring implementation                      |
| `serialization.py`           | Supabase-safe upsert & validation               |

---

## 👤 User Memory Management

- LLM analyzes each user message for significant facts  
- Filters out trivial or redundant info  
- Updates stored only on logout (bulk flush)  
- Real-time memory sync happens in Redis during session  

---

## 📝 Example `.env` File

```env
GOOGLE_API_KEY=your_google_genai_api_key

SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_service_role_key

RABBITMQ_URL=amqp://guest:guest@rabbitmq-host:5672/
RABBITMQ_API_URL=http://rabbitmq-host:15672/api/queues
RABBITMQ_API_USER=guest
RABBITMQ_API_PASS=guest

CLEANUP_INTERVAL_SEC=60

REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
```

---

## ⚠️ Notes

- Never commit actual API keys or credentials  
- You are responsible for providing your own:
  - Google GenAI access  
  - Supabase instance  
  - Redis & RabbitMQ setup
