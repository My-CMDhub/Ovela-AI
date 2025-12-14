# Ovela AI - Intelligent Receptionist for Beauty Studios

![Ovela AI Banner](public/og-image.png)

Ovela is an AI-powered receptionist designed specifically for beauty and hair studios. It automates client communication, booking management, and scheduling, allowing studio owners to focus on their craft.

## 🚀 Features

- **AI Receptionist**: Automates responses to client inquiries via SMS/WhatsApp (planned).
- **Smart Scheduling**: Seamless booking management integrated with studio calendars.
- **Waitlist System**: Capture early interest with a high-converting waitlist form.
- **Automated Onboarding**: Instant welcome emails with personalized details via Resend.
- **Dark Mode**: Fully responsive UI with seamless light/dark mode switching.

## 🛠️ Tech Stack

### Frontend
- **Framework**: [Next.js 14](https://nextjs.org/) (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS + Framer Motion (Animations)
- **UI Components**: Radix UI + Lucide Icons

### Backend & Infrastructure
- **BaaS**: [Appwrite](https://appwrite.io/) (Database, Functions, Auth)
- **Email**: [Resend](https://resend.com/) (Transactional Emails)
- **Hosting**: Vercel (Frontend) + Appwrite Cloud (Backend)

## 📂 Project Structure

```bash
├── app/                  # Next.js App Router pages
├── components/           # Reusable UI components
│   ├── ui/               # Primitive UI elements (buttons, inputs)
│   └── ...               # Feature-specific components (Hero, Contact)
├── lib/                  # Utility functions & Appwrite config
├── public/               # Static assets (images, icons)
├── appwrite-function/    # Serverless function for email automation
│   └── src/
│       └── main.js       # Email logic (Node.js)
└── ...
```

## ⚡️ Getting Started

### Prerequisites
- Node.js 18+
- Appwrite Cloud Account
- Resend API Key

### 1. Clone the repository
```bash
git clone https://github.com/yourusername/ovela-ai.git
cd ovela-ai
```

### 2. Install dependencies
```bash
npm install
```

### 3. Environment Setup
Create a `.env` file in the root directory:

```env
NEXT_PUBLIC_APPWRITE_ENDPOINT=https://cloud.appwrite.io/v1
NEXT_PUBLIC_APPWRITE_PROJECT_ID=your_project_id
NEXT_PUBLIC_APPWRITE_DATABASE_ID=your_database_id
NEXT_PUBLIC_APPWRITE_COLLECTION_ID=your_collection_id
```

### 4. Run Development Server
```bash
npm run dev
```
Visit `http://localhost:3000` to see the app.

## ☁️ Appwrite Function (Email Automation)

The email automation logic lives in `appwrite-function/`. It triggers whenever a new document is created in the `clients` collection.

### Deployment
1. Navigate to the function directory:
   ```bash
   cd appwrite-function
   ```
2. Create a deployment archive:
   ```bash
   tar -czf ../waitlist-function.tar.gz package.json src
   ```
3. Upload `waitlist-function.tar.gz` to Appwrite Console → Functions.

### Environment Variables (Appwrite Console)
- `RESEND_API_KEY`: Your Resend API key
- `FROM_EMAIL`: `hello@ovela.dev`
- `ADMIN_EMAIL`: Your email for notifications

## 🚢 Deployment

The frontend is optimized for **Vercel**.

1. Push code to GitHub.
2. Import project in Vercel.
3. Add environment variables.
4. Deploy! 🚀

## 📄 License

This project is proprietary and confidential. Unauthorized copying of this file, via any medium is strictly prohibited.

---

**Built with ❤️ by the Ovela Team**
