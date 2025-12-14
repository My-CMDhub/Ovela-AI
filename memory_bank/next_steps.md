# Next Steps - Ovela Launch & Enhancement Roadmap

**Current Priority**: 🚀 **LAUNCH READINESS**

---

## 🚀 Phase 0: Immediate Launch Readiness (This Week)

### 0.1 **Email Identity Logic Implementation**
- **Goal**: Ensure email sender identity matches the recipient's context.
- **Rules**:
  - **To Owner**: Emails come from "Ovela Business" (Platform notification).
    - *Template*: "Client X has cancelled their appointment..."
  - **To Customer**: Emails come from "Business Owner Name" (White-label experience).
    - *Template*: "Your appointment with [Business Name] has been cancelled..."
- **Task**: Update `backend/services/email.py` and `dashboard.py` logic.

### 0.2 **Comprehensive Security Audit**
- **Credential Check**: Scan codebase for hardcoded keys/secrets.
- **API Exposure**: Verify `FastAPI` docs don't expose sensitive internal endpoints.
- **Database Security**: 
  - Enable RLS (Row Level Security) on Appwrite collections if possible.
  - Verify API Key scopes are minimal (only needed permissions).
- **Frontend Security**:
  - Check for exposed env vars in Next.js public config.
  - Verify headers (CORS, CSP).

### 0.3 **Client Onboarding & Scaling Plan**
- **Single Client Onboarding Flow**:
  1. Create Business Doc in Appwrite.
  2. Configure Twilio Number & WhatsApp Profile.
  3. Set "Fixed" Industry (e.g., Beauty).
  4. Handover Credentials / specific URL.
- **Future Multi-Tenant Plan**:
  - Automate sub-account creation.
  - Self-serve onboarding wizard.

### 0.4 **Deployment Readiness**
- **Backend (Heroku)**:
  - Verify `Procfile` and `requirements.txt`.
  - Check Env Var propagation.
  - Test Webhook latency.
- **Frontend (Vercel)**:
  - Verify Build pipeline.
  - Check Domain DNS propagation.
  - Verify `NEXT_PUBLIC_API_URL` connectivity to Heroku.

### 0.5 **Testing Strategy**
- **Manual WhatsApp Testing**:
  - Test Flow: Booking -> Reschedule -> Cancel.
  - Test Edge Cases: Invalid dates, "speak to human", emoji spam.
- **Automated Script Testing**:
  - `test_security.py`: Try to access admin endpoints without auth.
  - `test_flow.py`: Simulate conversation loads.
- **AI Agent Verification**:
  - Verify AI doesn't "break character" or reveal system prompt info.

### 0.6 **Final Provisioning Checklist**
- [ ] **Twilio**: Purchase dedicated number for client WhatsApp.
- [ ] **Meta**: Verify Business Profile Display Name matches client.
- [ ] **Call Forwarding**:
  - *Instruction*: "Set up conditional call forwarding (Busy/No Answer) to [Twilio Number]."
  - *Carrier Specifics*: Telstra/Optus/Vodafone codes (`*61*...`).

---

## 🎯 Phase 1: Backend Modularization & Scalability

### 1.1 **Refactor `dashboard.py` into Modular Architecture**
**Proposed Structure**:
```
backend/api/
├── dashboard/
│   ├── __init__.py
│   ├── bookings.py      # Booking CRUD operations
│   ├── settings.py      # Business configuration
│   └── ...
```

---

## 🎨 Phase 2: Next-Level Industry Theming

### 2.1 **Industry-Specific Dashboard Layouts**
- **Health**: Show patient queue, urgent flags
- **Fitness**: Show class capacity, member check-ins

### 2.2 **Custom Chart Colors**
- Analytics charts use industry theme colors

---

## 📊 Phase 3: Advanced Analytics & Features

### 3.1 **Revenue Tracking**
- Add `price` field to services.
- Calculate daily/weekly/monthly revenue.

### 3.2 **Enhanced Notifications**
- SMS fallback for urgent cancellations.
- Push notifications support.

---
**Note**: Complete Phase 0 before moving to feature expansion.
