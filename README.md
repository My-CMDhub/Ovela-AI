# Ovela AI - Intelligent Receptionist for Beauty Studios

![Ovela AI](frontend/public/file.svg)

Ovela is an AI-powered receptionist designed specifically for beauty and hair studios. It automates client communication, booking management, and scheduling via WhatsApp and a modern web dashboard.

## 📂 Project Structure

This project is a **Monorepo** containing both the frontend and backend applications.

```bash
├── frontend/                   # Next.js 14 Dashboard & Landing Page (TypeScript, Tailwind)
│   ├── app/                    # Next.js App Router (Pages, Layouts, Routing)
│   │   ├── admin/              # Admin dashboard pages
│   │   ├── dashboard/          # Client dashboard pages
│   │   ├── login/              # Login routes & handlers
│   │   ├── globals.css         # Styling system & design tokens
│   │   ├── layout.tsx          # Main HTML structure, contexts, providers
│   │   └── page.tsx            # Landing Page root
│   ├── components/             # Reusable UI Components (buttons, dialogs, visualizers)
│   ├── contexts/               # React Contexts (auth, webhooks, voice settings)
│   ├── hooks/                  # Custom React hooks
│   ├── lib/                    # Shared utility files (appwrite client configuration)
│   └── package.json            # Node.js configurations & scripts
│
├── backend/                    # Python FastAPI Backend
│   ├── api/                    # Endpoint Routes (FastAPI APIRouter)
│   │   ├── actions.py          # Triggered workflow events (booking updates, reminders)
│   │   ├── voice.py            # Twilio media stream WebSockets & demo approval hooks
│   │   ├── dashboard.py        # Studio dashboard CRUD backend
│   │   ├── twilio.py           # Twilio telephony webhooks
│   │   └── stripe.py           # Payment processing integration
│   ├── core/                   # Core Configuration & Security
│   │   ├── ai/                 # AI Orchestrations & Prompts
│   │   │   ├── orchestrator.py # Orchestrator deciding manager vs worker logic
│   │   │   ├── prompts.py      # Base instruction sets & context rules
│   │   │   └── handlers.py     # Callback handlers for LLM outputs
│   │   ├── config.py           # System env configurations & API keys
│   │   └── security.py         # Authentication tokens & encryption helper
│   ├── services/               # Integrations & Business Logic
│   │   ├── appwrite.py         # Appwrite DB Client & query wrappers
│   │   ├── voice_agent/        # The Voice Stream processing engine
│   │   │   ├── handler.py      # Audio frames transceiver & Deepgram adapter
│   │   │   ├── prompts.py      # System personas for voice assistants
│   │   │   └── bridges/        # Deepgram and Twilio stream managers
│   │   ├── email.py            # Email senders (Resend API)
│   │   ├── memory.py           # Caching & context matching
│   │   └── scheduled_jobs/     # Outbound SMS/WhatsApp schedulers
│   ├── main.py                 # FastAPI Main Entrypoint (Routes mount, CORS, startup)
│   └── requirements.txt        # Python packages & dependencies
│
├── memory_bank/                # Living Documentation & Handoffs
│   ├── ACTIVE_PLAN.md          # Granular current task checklists & upcoming tasks
│   ├── COMPLETED_STATUS.md     # Factual record of completed items & historical decisions
│   ├── CURRENT_STATUS.md       # Tech stack, architecture diagrams, and Active Risks
│   ├── IMPLEMENTATION_ARTIFACT.md # Broad plan (current + future plans) & milestones
│   └── END_SESSION.md          # Handoff context & restoration targets for next sessions
└── docs/                       # Design documents & Challenge Resources
    └── AI Challenge/
        ├── Additional_Context.md
        └── ai_agents_challenge_designed_guide.pdf
```

## 🚀 Getting Started

### Prerequisites
- Node.js 18+
- Python 3.10+
- Appwrite Cloud Account
- OpenAI API Key
- Meta Developers Account (WhatsApp API)
- Twilio Account (Voice/SMS)
- Resend Account (Emails)

---

### 1. Installation

**Clone the repository:**
```bash
git clone https://github.com/YourUsername/Ovela-AI.git
cd Ovela-AI
```

#### Frontend Setup
```bash
cd frontend
npm install
```

#### Backend Setup
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

---

### 2. Environment Configuration

#### Frontend (`frontend/.env.local`)
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_APPWRITE_ENDPOINT=https://cloud.appwrite.io/v1
NEXT_PUBLIC_APPWRITE_PROJECT_ID=your_project_id
```

#### Backend (`backend/.env`)
See `backend/.env.example` for the full list.
```env
OPENAI_API_KEY=sk-...
META_ACCESS_TOKEN=...
APPWRITE_PROJECT_ID=...
RESEND_API_KEY=...
```

---

### 3. Running Locally

**Terminal 1: Backend**
```bash
cd backend
source .venv/bin/activate
uvicorn main:app --reload
# Running on http://localhost:8000
```

**Terminal 2: Frontend**
```bash
cd frontend
npm run dev
# Running on http://localhost:3000
```

---

## 🚢 Deployment

### Backend (Heroku)
The backend is configured for Heroku deployment.

1. **Create App:** `heroku create ovela`
2. **Set Env Vars:** Add all variables from `backend/.env` to Heroku Config Vars.
3. **Deploy:**
   ```bash
   # Deploy only the backend folder
   git subtree push --prefix backend heroku main
   ```

### Frontend (Vercel)
The frontend is optimized for **Vercel**.

1. **Import Project:** Select your GitHub repo.
2. **Root Directory:** Edit settings to point to `frontend`.
3. **Env Vars:** Add production variables (e.g., `NEXT_PUBLIC_API_URL` -> Heroku URL).
4. **Deploy!** 🚀

---

## 🛠️ Tech Stack

- **Frontend**: Next.js 14, TypeScript, Tailwind CSS, Framer Motion
- **Backend**: Python FastAPI, Uvicorn
- **AI**: OpenAI GPT-4o (Function Calling)
- **Database**: Appwrite
- **Communication**: WhatsApp Cloud API, Twilio Voice, Resend Email

---

**Built with ❤️ by the Ovela Team**
