"use client"

import { IndustryTemplate } from "@/components/industry-template"
import { Building2, Key, Moon, ShieldCheck, Phone } from "lucide-react"
import { MotelVisual } from "@/components/industry-visuals"

export default function MotelsPage() {
    return (
        <IndustryTemplate
            industry="Motels & Accommodation"
            heroVisual={<MotelVisual />}
            heroTitle={
                <>
                    The Front Desk That <br />
                    <span className="italic text-muted-foreground">Never Sleeps.</span>
                </>
            }
            heroSubtitle="Automate after-hours check-ins, guest inquiries, and direct bookings. Maintain 24/7 responsiveness without the overhead of night staff."
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
                    description: "Ovela handles late arrivals, verifies details, and can dispatch digital key codes (via integration) without waking you up.",
                    icon: <Moon className="w-5 h-5" />
                },
                {
                    title: "OTA Commission Defense",
                    description: "Capture guests calling to check rates. Ovela books them directly into your PMS, saving 15-20% in commissions.",
                    icon: <ShieldCheck className="w-5 h-5" />
                },
                {
                    title: "Smart Policy Answers",
                    description: "The AI knows your specific rules on pets, parking, and late check-outs, providing instant, accurate answers 24/7.",
                    icon: <Building2 className="w-5 h-5" />
                }
            ]}
            workflowTitle="Night Audit Mode"
            workflowDescription="When your staff goes home, Ovela wakes up. It acts as a full tier-1 support agent, handling 90% of inquiries and only escalating genuine emergencies to your mobile."
            ctaText="Secure Your Front Desk"
        />
    )
}
