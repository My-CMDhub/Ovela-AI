"use client"

import { IndustryTemplate } from "@/components/industry-template"
import { Zap, Calendar, ClipboardCheck } from "lucide-react"
import { EnergyVisual } from "@/components/industry-visuals"

export default function EnergyPage() {
    return (
        <IndustryTemplate
            industry="Energy & Utilities"
            heroVisual={<EnergyVisual />}
            heroTitle={
                <>
                    Energy Operations <br />
                    <span className="italic text-muted-foreground">On Autopilot.</span>
                </>
            }
            heroFocusSentence="{Scale|Drive|Power} {Growth|Efficiency|Impact}"
            heroSubtitle="Automate VEU rebate scheduling, solar installation bookings, and eligibility checks. Stop chasing leads and start closing deals."
            painPoints={[
                {
                    label: "Missed Rebate Deadline",
                    problem: "Manual scheduling leads to missed government rebate windows and lost client trust.",
                },
                {
                    label: "Eligibility Pong",
                    problem: "Wasting hours verifying if a client qualifies for solar or LED upgrades costs you money.",
                },
                {
                    label: "Scheduling Chaos",
                    problem: "Coordinating installers with homeowners via phone tag is a full-time job you don't need.",
                }
            ]}
            valueProps={[
                {
                    title: "Instant Eligibility Checks",
                    description: "Ovela asks the right questions upfront to verify government rebate eligibility before you roll a truck.",
                    icon: <ClipboardCheck className="w-5 h-5" />
                },
                {
                    title: "Smart Installer Dispatch",
                    description: "Automatically book site audits and installations directly into your team's calendar.",
                    icon: <Calendar className="w-5 h-5" />
                },
                {
                    title: "24/7 Lead Capture",
                    description: "Capture solar leads instantly, even when they call at 8 PM after seeing your ad.",
                    icon: <Zap className="w-5 h-5" />
                }
            ]}
            workflowTitle="The Audit Workflow"
            workflowDescription="From initial inquiry to confirmed installation date, Ovela handles the logistics so your installers can focus on the work."
            ctaText="Energize Your Operations"
        />
    )
}
