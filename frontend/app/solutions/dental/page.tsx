"use client"

import { IndustryTemplate } from "@/components/industry-template"
import { Activity, CalendarClock, DollarSign, HeartPulse } from "lucide-react"
import { DentalVisual } from "@/components/industry-visuals"

export default function DentalPage() {
    return (
        <IndustryTemplate
            industry="Dental Clinics"
            heroVisual={<DentalVisual />}
            heroTitle={
                <>
                    Clinical Focus, <br />
                    <span className="italic text-muted-foreground">Admin Precision.</span>
                </>
            }
            heroFocusSentence="{Precision|Gentle|Quality} {Dentistry|Treatment|Trust}"
            heroSubtitle="Stop interrupting procedures to answer the phone. Ovela triages emergencies, filters price shoppers, and fills your calendar with high-value appointments."
            painPoints={[
                {
                    label: "The Chair-Side Interruption",
                    problem: "Leaving a patient in the chair to answer a ringing phone is unprofessional and inefficient.",
                },
                {
                    label: "Lost Emergency Revenue",
                    problem: "Patients in pain don't leave voicemails. They call the next dentist on Google.",
                },
                {
                    label: "Endless Price Shopping",
                    problem: "Front desk time wasted quoting extraction prices to people who never book.",
                }
            ]}
            valueProps={[
                {
                    title: "Intelligent Triage",
                    description: "Ovela distinguishes between a chipped tooth emergency and a routine cleaning request, prioritizing accordingly.",
                    icon: <HeartPulse className="w-5 h-5" />
                },
                {
                    title: "Gap Filling",
                    description: "Got a last-minute cancellation? Ovela can actively reach out to your waitlist to fill the slot (Coming Soon).",
                    icon: <CalendarClock className="w-5 h-5" />
                },
                {
                    title: "High-Value Conversion",
                    description: "The AI is trained to convert inquiries into consultations, not just give out prices. It secures the booking.",
                    icon: <DollarSign className="w-5 h-5" />
                }
            ]}
            workflowTitle="The Silent Partner"
            workflowDescription="Seamlessly integrated with Practice Management Software. Ovela handles the intake, checks availability, and inserts the appointment directly into your book."
            ctaText="Optimize Your Clinic"
        />
    )
}
