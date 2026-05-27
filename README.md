# AutoReply AI 🤖

An intelligent, multi-channel customer support automation platform that handles WhatsApp, email, and voice queries 24/7 using AI — trained on your own business knowledge base.

---

## 🚀 Features

### 💬 Multi-Channel Support
- **WhatsApp** — instant AI replies via Twilio WhatsApp sandbox
- **Email** — automated email responses via SendGrid inbound parsing
- **Voice** — text-to-speech phone support via Twilio Voice with speech recognition

### 🧠 AI Brain (LangGraph + Groq)
- Powered by **Groq's llama-3.3-70b-versatile** for ultra-fast LLM inference
- Built with **LangGraph** for structured agentic reasoning
- Structured JSON output with intent classification, confidence scoring, and lead extraction
- Automatic retry on malformed output (up to 3 attempts before escalation)
- Circuit breaker pattern to handle LLM failures gracefully

### 📚 Knowledge Base & RAG
- Upload your own FAQ or business document (`.txt`, `.pdf`, `.docx`)
- Automatically chunked and embedded using **sentence-transformers (paraphrase-MiniLM-L3-v2)**
- Stored in **ChromaDB** for fast vector similarity search
- Retrieval Augmented Generation (RAG) ensures answers come from your actual business content
- Configurable similarity threshold and chunk size

### 🎯 Intent Classification
Every message is classified into one of:
- `pricing_inquiry` — cost, fees, packages
- `product_info` — what you offer, features
- `booking_request` — appointments, demos
- `complaint` — issues, refunds, problems
- `general_query` — general questions
- `human_request` — customer wants a human agent
- `greeting` — hello, hi
- `unknown` — cannot determine

### 👤 Lead Extraction
- Automatically extracts customer name, phone, and email if voluntarily shared
- Never asks for personal info unless directly relevant
- All extracted leads stored and visible in the dashboard

### 🚨 Smart Escalation
- Escalates to human agent when:
  - Customer explicitly requests a human
  - Customer is angry or abusive
  - AI confidence is below threshold (0.4)
  - Query involves legal, medical, or financial advice
  - Complaint cannot be resolved from knowledge base
- Human-friendly escalation message sent to customer automatically
- All escalations logged with reason and visible in dashboard

### 🕐 Working Hours Awareness
- Configurable working hours per business (e.g. Mon–Sat, 9AM–6PM)
- After-hours suffix appended to replies informing customers of availability
- AI still responds 24/7 but flags out-of-hours context

### 🛡️ Security
- Prompt injection detection and neutralization (14 attack patterns)
- Customer message sanitized before LLM — never injected into system prompt
- Input length limited to 1000 characters
- HTML/script tag stripping

### 📊 Dashboard (Frontend)
- Overview stats: total conversations, leads, escalations, notifications
- Conversation list with channel, status, and customer info
- Escalation management — view open escalations and mark as resolved
- Knowledge Base management — upload, view, and delete FAQ files
- Real-time notifications panel

### ⚙️ Business Profile Configuration
- Business name, industry, description
- Bot tone (professional / friendly / casual)
- Bot language (English / Hindi / Telugu)
- Working hours and days
- Custom fallback message for escalations

---

## 🏗️ Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI (Python) |
| AI Agent | LangGraph |
| LLM | Groq (llama-3.3-70b-versatile) |
| Vector DB | ChromaDB (persistent) |
| Embeddings | sentence-transformers (paraphrase-MiniLM-L3-v2) |
| Database | Supabase (PostgreSQL) |
| WhatsApp | Twilio WhatsApp |
| Voice | Twilio Voice (TTS + STT) |
| Email | SendGrid Inbound Parse |
| Deployment | Railway |
| Frontend | React (separate repo) |

---

## 📁 Project Structure

```
app/
├── main.py                  # FastAPI app entry point
├── middleware.py            # Request logging middleware
├── agents/
│   └── ai_brain.py          # LangGraph agent — core AI logic
├── api/
│   ├── auth.py              # Authentication endpoints
│   ├── dashboard.py         # Dashboard API endpoints
│   ├── knowledge.py         # Knowledge base upload/list/delete
│   ├── test_system.py       # System test endpoints
│   └── webhooks.py          # Twilio & SendGrid webhook receivers
├── config/
│   └── settings.py          # Centralised configuration (Pydantic)
├── models/
│   └── database.py          # Supabase client + query helpers
├── prompts/
│   └── ai_brain_prompt.py   # All LLM prompts (never inline)
├── schemas/                 # Pydantic request/response schemas
├── services/
│   ├── email_handler.py     # Email processing service
│   ├── knowledge_service.py # KB chunking, embedding, ChromaDB storage
│   ├── voice.py             # Voice call handling (TTS/STT)
│   └── whatsapp.py          # WhatsApp message handling
└── utils/
    ├── circuit_breaker.py   # Circuit breaker for external services
    ├── exceptions.py        # Custom exceptions
    └── logger.py            # Structured logging (structlog)
```

---

## 🔧 Environment Variables

```env
# App
SECRET_KEY=

# Groq
GROQ_API_KEY=gsk_...

# Supabase
SUPABASE_URL=https://...
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_KEY=eyJ...

# Twilio
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=
TWILIO_PHONE_NUMBER=
TWILIO_WHATSAPP_SANDBOX=+14155238886

# SendGrid
SENDGRID_API_KEY=SG....
SENDGRID_FROM_EMAIL=

# CORS
FRONTEND_URL=https://your-frontend.com

# Railway public URL (for voice gather webhook)
NGROK_URL=https://your-backend.up.railway.app
```

---

## 🚀 Deployment (Railway)

1. Push code to GitHub
2. Connect repo to Railway
3. Add all environment variables in Railway → Variables
4. Railway auto-deploys on every push
5. After each deploy — go to Dashboard → Knowledge Base → re-upload your FAQ file (ChromaDB is ephemeral on Railway)

---

## 📋 Knowledge Base Upload

1. Prepare a `.txt`, `.pdf`, or `.docx` file with your business FAQ
2. Go to Dashboard → Knowledge Base → Upload
3. Wait for `kb_training_completed` confirmation
4. The AI will now answer from your actual business content

**Recommended format:**
```
Q: What is your return policy?
A: We offer a 7-day easy return policy...

Q: How do I track my order?
A: Once shipped, you will receive a tracking link...
```

---

## 🔄 How It Works

```
Customer Message (WhatsApp / Email / Voice)
        ↓
Webhook received → sanitize input
        ↓
Fetch conversation history (last 10 messages)
        ↓
RAG retrieval → search ChromaDB for relevant KB chunks
        ↓
Build system prompt (business info + KB context + channel rules)
        ↓
Groq LLM → structured JSON response
        ↓
Validate output → check confidence & escalation flag
        ↓
If escalate=true → log escalation + notify dashboard
        ↓
Send reply via Twilio / SendGrid
        ↓
Save conversation + messages to Supabase
```

---

## 📄 License

MIT License — feel free to use and modify.
