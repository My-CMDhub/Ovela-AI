# Ovela AI - Intelligent Receptionist for Beauty Studios

![Ovela AI](frontend/public/file.svg)

Ovela is an AI-powered receptionist designed specifically for beauty and hair studios. It automates client communication, booking management, and scheduling via WhatsApp and a modern web dashboard.

## 📂 Project Structure

This project is a **Monorepo** containing both the frontend and backend applications.

```bash
├── frontend/           # Next.js 14 Dashboard & Landing Page
│   ├── app/            # App Router pages
│   ├── components/     # UI components
│   └── ...
├── backend/            # FastAPI Python Backend
│   ├── core/           # AI Logic & Config
│   ├── services/       # Integrations (Twilio, Meta, Appwrite, Resend)
│   └── main.py         # API Entry point
└── ...
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
