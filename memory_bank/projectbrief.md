# Project Brief: Ovela AI

## Vision
**Ovela AI** is a text-based Virtual AI Receptionist designed for Australian businesses on WhatsApp.
While initially focused on Beauty Salons, the system is architected to scale to other "crowded industries" (e.g., Dental, Real Estate) where appointment management is critical.

## Core Problem
Businesses lose potential customers when they cannot answer calls or messages immediately. A human receptionist is expensive and not 24/7.

## Solution
An automated AI agent on WhatsApp that can:
1.  Answer inquiries instantly (Pricing, Location, Services).
2.  Check availability and Book appointments (Native Appwrite System).
3.  Manage rescheduling and cancellations.
4.  Adopt different "personas" based on the industry context.

## Technology Stack
*   **Interface**: WhatsApp (via Meta Cloud API)
*   **Backend**: Python FastAPI (High performance, Async, AI-ready)
*   **Database**: Appwrite (Conversations, Businesses, Bookings)
*   **Intelligence**: OpenAI GPT-4o
*   **Frontend**: Next.js (Admin Dashboard & Landing Page - *Currently `ovela-ai` folder*)

## Key Constraints
*   **Region**: Australia (AU context for privacy/compliance).
*   **Scalability**: Must support multi-tenancy (multiple businesses using one system).
*   **Reliability**: Must handle webhook failures and maintain conversation context.
