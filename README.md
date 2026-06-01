# Ovela AI - Voice Reservation Agent for B2B Hospitality

![Ovela AI Dashboard](frontend/public/file.svg)

**Ovela AI** is an ultra-low latency, multi-agent conversational voice receptionist designed for B2B hospitality (motels and boutique hotels). It autonomously handles reservations, negotiates room availability directly against the Property Management System (PMS), processes Stripe payments, and answers complex policy questions.

This project was built for the **Google for Startups AI Agents Challenge 2026** (Track 2: Optimize).

### 🏆 AI Agents Challenge — Optimization Results
By migrating our core reasoning engine to the **Gemini Enterprise Agent Development Kit (ADK)**, we transformed our flat-prompt baseline into a robust multi-agent graph, boosting our evaluation pass rate significantly while eliminating hallucination traps.

* **Baseline (no ADK):** ~72.4 avg score
* **Optimized (Gemini 2.5 Flash + ADK):** 84.1 avg score **(+11.7 pts)**
* *The evaluation harness uses adversarial simulations to test interruption resilience, date ordinal typos, and background noise.*

---

## 🧠 The Architecture: Hot Path vs. Cold Path
To achieve industry-leading audio latency (<850ms) while maintaining 100% Gemini compliance on business logic, we enforce a strict architectural boundary:

1. **Hot Path (Real-time Voice Stream):** Twilio WebSockets → FastAPI Audio Bridge → Deepgram Voice Agent API. 
   - Uses `gpt-4.1-nano` purely as the conversational entry gate because Deepgram's hosted Google provider lacks Vertex ADC support. This layer manages VAD (Voice Activity Detection), TTS via Cartesia Sonic-3, and STT via Deepgram Nova-2.
2. **Cold Path (ADK Reasoning Graph — 100% Gemini):** All business logic, PMS operations, and multi-agent intelligence route asynchronously to the Google ADK graph.
   - Runs exclusively on **Gemini 2.5 Flash via Vertex AI (ADC authentication)**.
   - **OvelaManager** coordinates routing to the **BookingWorker** (PMS/Stripe) and **InfoWorker** (Policies/Search Grounding).
   - Session state is persisted natively via `AppwriteSessionService`.

### Architecture Diagram

```mermaid
graph TD
    User((Guest)) -- Voice --> Twilio[Twilio WebSockets]
    
    subgraph Hot Path <850ms Latency
        Twilio <--> FastAPI[FastAPI Audio Bridge]
        FastAPI <--> Deepgram[Deepgram Voice Agent]
        Deepgram -. STT/VAD .-> GPT4[gpt-4.1-nano]
        Deepgram -. TTS .-> Cartesia[Cartesia Sonic-3]
    end
    
    subgraph Cold Path 100% Gemini
        Deepgram -- Intent Trigger --> OvelaManager[OvelaManager LlmAgent]
        OvelaManager <--> BookingWorker[BookingWorker LlmAgent]
        OvelaManager <--> InfoWorker[InfoWorker LlmAgent]
        InfoWorker -. Search .-> Google[Google Search Grounding]
        BookingWorker -. Payment .-> Stripe[Stripe Checkout]
        BookingWorker -. Persist .-> Appwrite[Appwrite DB]
    end
    
    OvelaManager -- Vertex AI ADC --> Gemini[Gemini 2.5 Flash]
    BookingWorker -- Vertex AI ADC --> Gemini
    InfoWorker -- Vertex AI ADC --> Gemini
```

---

## 🚀 Judge & Testing Guide

Want to experience the ultra-low latency voice agent yourself? 
**Call the live agent (Australia ONLY):** *(Phone number provided in Devpost Submission)*
*(Note: To prevent toll fraud and ensure token efficiency, inbound/outbound routing is restricted to Australian numbers.)*

### Prerequisites
- Node.js 18+
- Python 3.10+
- Google Cloud Project with Vertex AI enabled
- Appwrite Cloud Account
- Stripe, Twilio, Deepgram, and Cartesia API Keys

### 1. Installation

**Clone the repository:**
```bash
git clone https://github.com/YourUsername/Ovela-AI.git
cd Ovela-AI
```

#### Backend Setup (FastAPI & ADK)
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

#### Frontend Setup (Next.js & Dashboard)
```bash
cd frontend
npm install
```

### 2. Environment Configuration
Credentials are managed via GCP Secret Manager in production. For local testing, copy `backend/.env.example` to `backend/.env`.

**Required APIs:**
* `GOOGLE_APPLICATION_CREDENTIALS` (or use active `gcloud auth application-default login`)
* `APPWRITE_PROJECT_ID` & `APPWRITE_API_KEY`
* `DEEPGRAM_API_KEY`
* `TWILIO_ACCOUNT_SID`
* `STRIPE_SECRET_KEY`

### 3. Running Locally

**Terminal 1: Backend (Uvicorn)**
```bash
cd backend
source .venv/bin/activate
uvicorn main:app --reload
```

**Terminal 2: Frontend (Next.js)**
```bash
cd frontend
npm run dev
```

---

## 🚢 Production Deployment (Google Cloud Run)
The backend is containerized and deployed natively on **Google Cloud Run**.

1. **Build & Push Docker Image:**
   ```bash
   gcloud builds submit --tag gcr.io/your-project/ovela-backend backend/
   ```
2. **Deploy Service:**
   ```bash
   gcloud run deploy ovela-backend \
     --image gcr.io/your-project/ovela-backend \
     --platform managed \
     --region australia-southeast1 \
     --set-secrets=...
   ```
3. **Application Default Credentials:** The Cloud Run service account is granted Vertex AI User roles, allowing keyless, secure authentication to the Gemini Enterprise ADK.

---

## 🛠️ Tech Stack & Ecosystem

- **Frontend**: Next.js 14, TypeScript, Tailwind CSS, Appwrite Web SDK
- **Backend**: Python FastAPI, Uvicorn, Google GenAI, `google-adk-python`
- **AI Reasoning**: Gemini 2.5 Flash (Vertex AI), Google Search Grounding
- **Voice / Telephony**: Twilio, Deepgram (STT/VAD), Cartesia Sonic-3 (TTS)
- **Database & Storage**: Appwrite Cloud
- **Infrastructure**: Google Cloud Run, GCP Secret Manager

---

**Built with ❤️ by the Ovela Team for the Google for Startups AI Agents Challenge**
