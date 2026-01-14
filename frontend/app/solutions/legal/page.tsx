"use client"

import { IndustryTemplate } from "@/components/industry-template"
import { Scale, Shield, FileText } from "lucide-react"
import { LegalVisual } from "@/components/industry-visuals"

export default function LegalPage() {
    return (
        <IndustryTemplate
            industry="Legal & Consultancy"
            heroVisual={<LegalVisual />}
            heroTitle={
                <>
                    Client Intake that <br />
                    <span className="italic text-muted-foreground">Builds Trust.</span>
                </>
            }
            heroFocusSentence="{Legal|Client|Case} {Strategy|Defense|Victory}"
            heroSubtitle="Automate client onboarding, conflict checks, and compliance verification. Secure, professional, and efficient legal intake 24/7."
            painPoints={[
                {
                    label: "Unqualified Leads",
                    problem: "Senior partners wasting billable hours on initial consults that go nowhere.",
                },
                {
                    label: "Compliance Bottlenecks",
                    problem: "Manual KYC and conflict checks slowing down client onboarding by days.",
                },
                {
                    label: "Missed Urgent Cases",
                    problem: "Calls outside office hours often involve urgent matters that need immediate triage.",
                }
            ]}
            valueProps={[
                {
                    title: "Smart Triage",
                    description: "Ovela screens potential clients for case type, budget, and urgency before they reach your calendar.",
                    icon: <Scale className="w-5 h-5" />
                },
                {
                    title: "Automated Compliance",
                    description: "Collect necessary details for conflict checks and KYC verification securely and automatically.",
                    icon: <Shield className="w-5 h-5" />
                },
                {
                    title: "Professional Onboarding",
                    description: "Give every caller a tier-1 professional experience, even when reception is closed.",
                    icon: <FileText className="w-5 h-5" />
                }
            ]}
            workflowTitle="The Intake Protocol"
            workflowDescription="Seamlessly integrate new clients into your practice management software with full transcripts and compliance preliminary checks done."
            ctaText="Secure Your Practice"
        />
    )
}
