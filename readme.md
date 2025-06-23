📋 # Prerequisites  
Before setting up the project, ensure you have the following installed:

- Python 3.9+  
- RabbitMQ Server with Management Plugin  
- Google GenAI API Key (for LLM and embedding services)  
- Supabase Account and Project Access  

---

🛠️ # Complete Setup Guide  

### Step 1: Clone and Setup Project Structure  

git clone <repository-url>  
cd mem0-async  

Your project structure should look like:  
mem0-async/  
├── chat-service/  
│   └── app/  
│       ├── __init__.py  
│       ├── main.py  
│       ├── chatbot.py  
│       ├── memory_functions.py  
│       └── worker.py  
├── .env  
├── requirements.txt  
└── README.md  

---

### Step 2: Create Virtual Environment  

**Create virtual environment**  
python -m venv venv  

**Activate virtual environment**  
- On Windows:  
  venv\Scripts\activate  
- On macOS/Linux:  
  source venv/bin/activate  

**Install the dependencies:**  
pip install -r requirements.txt  

---

### Step 3: Environment Configuration  

Create a `.env` file in the project root with the following structure (replace with your actual credentials):  

#Google API credentials  
GOOGLE_API_KEY=your_google_api_key_here  

#Supabase Database credentials  
SUPABASE_URL=https://your-project.supabase.co  
SUPABASE_KEY=your_supabase_anon_key_here  

#RabbitMQ connection settings  
RABBITMQ_URL=amqp://guest:guest@localhost:5672/  
RABBITMQ_HOST=localhost  
RABBITMQ_PORT=5672  
RABBITMQ_USER=guest  
RABBITMQ_PASSWORD=guest  

#Application settings  
ENV=development  
LOG_LEVEL=debug  

---

### Step 4: RabbitMQ setup  

1. Install RabbitMQ and also its management plugin.  
2. Start the RabbitMQ server.  

**Create Required Queue:**  
- Open RabbitMQ Management Interface: http://localhost:15672  
- Login with default credentials: guest / guest  
- Navigate to Queues tab  
- Click "Add a new queue"  
- Configure queue:  
  - Name: memory_tasks  
  - Durability: Durable (survives server restarts)  
  - Auto delete: No  
- Click "Add queue"  

---

🚀 # Running the Application  

### System Architecture Flow  
The system follows this workflow:  
1) User Input → FastAPI chat endpoint receives message  
2) Immediate Response → Chat service calls LLM and returns reply  
3) Task Enqueue → Chat service publishes memory-processing task to RabbitMQ  
4) Background Processing → Memory worker consumes task and updates memories  
5) Persistence → New memories stored in Supabase for future context  

---

### Step 5: Start Memory Worker Service  

Open Terminal/PowerShell in project directory:  
cd chat-service  
python -m app.worker  

**Expected Output:**  
🔄 Memory worker started. Waiting for messages...

---

### Step 6: Start Chat Service  

Open another Terminal/PowerShell in mem0-async/chat-service:  
uvicorn chat-service.app.main:app --reload --host 127.0.0.1 --port 8001  

**Expected Output:**  
INFO:     Uvicorn running on http://127.0.0.1:8001 (Press CTRL+C to quit)  
INFO:     Started reloader process  
INFO:     Started server process  
INFO:     Waiting for application startup.  

---

### Step 7: 🧪 Testing the System  

**Access Swagger UI**  
Open your browser and navigate to: http://127.0.0.1:8001/docs  

You'll see the interactive API documentation with available endpoints  

**Test Chat Functionality**  
Using Swagger UI (Recommended):  
- Expand the /chat endpoint  
- Click "Try it out"  
- Enter test data by replacing 'string' in the JSON format provided.  
  {"user_id": "string", "user_input": "string"}  
- Click execute  
- Observe the response with the bot's reply  

**Memory Worker Console**  
Watch for processing logs: In the terminal where worker.py was run, we will get log.  

(Example)  
🛠️ Memory added.  
✅ Processed task for test_user  

The corresponding changes will be reflected in supabase as well.
