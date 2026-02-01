"use client"

import { IndustryTemplate } from "@/components/industry-template"
import { Building2, Key, Moon, ShieldCheck, Phone } from "lucide-react"
import { MotelVisual } from "@/components/industry-visuals"

export default function MotelsPage() {
    return (
        <IndustryTemplate
            industry="Motels & Accommodation"
            heroVisual={<MotelVisual />}
            heroTitle="The Front Desk That"
            heroFocusSentence="{Never|Always|Truly} {Sleeps|Welcomes|Works}"
            heroSubtitle="Automate 24/7 guest support, booking inquiries, and check-out coordination. Native 2-way sync with RMS Cloud, Cloudbeds, and Apaleo."
            painPoints={[
                {
                    label: "The 2:00 AM Lockout",
                    problem: "Waking up to handle lost keys or confused late arrivals costs you sleep and sanity.",
                },
                {
                    label: "Repetitive Policy Questions",
                    problem: "Answering \"What time is check-out?\" and \"Are you dog friendly?\" distracts from high-value work.",
                },
                {
                    label: "Missed Direct Bookings",
                    problem: "Every unanswered call sends a potential guest back to a high-commission OTA.",
                }
            ]}
            valueProps={[
                {
                    title: "After-Hours Gatekeeper",
                    description: "Ovela handles late arrivals, verifies details in RMS Cloud/Cloudbeds, and can dispatch digital key codes without waking you up.",
                    icon: <Moon className="w-5 h-5" />
                },
                {
                    title: "OTA Commission Defense",
                    description: "Capture guests calling to check rates. Ovela books them directly into your PMS (RMS/Cloudbeds), saving 15-20% in commissions.",
                    icon: <ShieldCheck className="w-5 h-5" />
                },
                {
                    title: "Smart Policy Answers",
                    description: "The AI knows your specific rules on pets, parking, and late check-outs, providing instant, accurate answers 24/7.",
                    icon: <Building2 className="w-5 h-5" />
                }
            ]}
            workflowTitle="Night Audit Mode"
            workflowDescription="When your staff goes home, Ovela wakes up. It acts as a full tier-1 support agent, handling 90% of inquiries and entering data directly into RMS Cloud or Cloudbeds."
            ctaText="Secure Your Front Desk"
        />
    )
}
