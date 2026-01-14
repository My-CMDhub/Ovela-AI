"use client"

import { IndustryTemplate } from "@/components/industry-template"
import { Users, FileText, PauseCircle, Timer } from "lucide-react"
import { PhysioVisual } from "@/components/industry-visuals"

export default function PhysioPage() {
    return (
        <IndustryTemplate
            industry="Physiotherapy & Allied Health"
            heroVisual={<PhysioVisual />}
            heroTitle={
                <>
                    Uninterrupted <br />
                    <span className="italic text-muted-foreground">Patient Care.</span>
                </>
            }
            heroFocusSentence="{Hands-on|Clinical|Expert} {Therapy|Recovery|Care}"
            heroSubtitle="Your hands should be on the patient, not the phone. Automate rescheduling, intake forms, and FAQs without hiring a full-time receptionist."
            painPoints={[
                {
                    label: "Session Fragmentation",
                    problem: "Answering calls during manual therapy breaks the flow and reduces treatment efficacy.",
                },
                {
                    label: "Phone Tag Rescheduling",
                    problem: "Wasting hours playing voicemail tag just to move an appointment from Tuesday to Thursday.",
                },
                {
                    label: "Admin Overload",
                    problem: "Spending your evenings returning calls and managing paperwork instead of resting.",
                }
            ]}
            valueProps={[
                {
                    title: "Zero-Interruption Policy",
                    description: "Let the phone ring. Ovela picks up instantly, handling the query so you can stay focused on the patient in front of you.",
                    icon: <PauseCircle className="w-5 h-5" />
                },
                {
                    title: "Smart Rescheduling",
                    description: "Patients can converse naturally to find a new time. \"Can I come in later?\" is handled instantly, updating your calendar.",
                    icon: <Timer className="w-5 h-5" />
                },
                {
                    title: "Intake Automation",
                    description: "Ovela collects key injury details during the call, so you have a preliminary SOAP note before they walk in.",
                    icon: <FileText className="w-5 h-5" />
                }
            ]}
            workflowTitle="Seamless Practice Flow"
            workflowDescription="From the initial injury inquiry to the booked appointment, Ovela manages the administrative patient journey."
            ctaText="Focus on Treatment"
        />
    )
}
