"use client"

import { IndustryTemplate } from "@/components/industry-template"
import { Home, Key, FileCheck } from "lucide-react"
import { RealEstateVisual } from "@/components/industry-visuals"

export default function RealEstatePage() {
    return (
        <IndustryTemplate
            industry="Real Estate & Property"
            heroVisual={<RealEstateVisual />}
            heroTitle={
                <>
                    Property Management <br />
                    <span className="italic text-muted-foreground">On Autopilot.</span>
                </>
            }
            heroFocusSentence="{Closing|Winning|Signing} {Deals|Clients|Trust}"
            heroSubtitle="Streamline rental applications, schedule inspections, and handle maintenance requests 24/7. Your digital property manager is here."
            painPoints={[
                {
                    label: "Endless Inquiries",
                    problem: "Taking hundreds of calls just to say 'Yes, the property is still available' drains your team.",
                },
                {
                    label: "Inspection No-Shows",
                    problem: "Manual confirmation calls take hours and people still forget to show up.",
                },
                {
                    label: "Maintenance Triage",
                    problem: "Emergency calls at 3 AM for a dripping tap? Let Ovela filter the real emergencies.",
                }
            ]}
            valueProps={[
                {
                    title: "Automated Viewing Booking",
                    description: "Prospective tenants can book inspection slots instantly without a single phone call.",
                    icon: <Key className="w-5 h-5" />
                },
                {
                    title: "Pre-Qualification",
                    description: "Ovela asks the hard questions first—income, rental history, pets—so you only deal with serious applicants.",
                    icon: <FileCheck className="w-5 h-5" />
                },
                {
                    title: "Maintenance Dispatch",
                    description: "Log maintenance requests, categorize priority, and dispatch trusted tradespeople automatically.",
                    icon: <Home className="w-5 h-5" />
                }
            ]}
            workflowTitle="The Leasing Loop"
            workflowDescription="Ovela handles the entire pre-leasing funnel, from inquiry to inspection, ensuring your property managers focus on owners and signing leases."
            ctaText="Upgrade Your Portfolio"
        />
    )
}
