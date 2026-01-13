"use client"

import { IndustryTemplate } from "@/components/industry-template"
import { Scissors, Calendar, CreditCard, Clock } from "lucide-react"
import { SalonVisual } from "@/components/industry-visuals"

export default function SalonsPage() {
    return (
        <IndustryTemplate
            industry="Salons & Barbershops"
            heroVisual={<SalonVisual />}
            heroTitle={
                <>
                    Protect Your <br />
                    <span className="italic text-muted-foreground">Chair Time.</span>
                </>
            }
            heroSubtitle="Eliminate the complexity of booking chemical services and enforcing deposits. Ovela understands service durations and protects your revenue."
            painPoints={[
                {
                    label: "Booking Complexity",
                    problem: "Clients booking a \"Cut\" when they need a \"Restyle & Color\" ruins your schedule.",
                },
                {
                    label: "The No-Show Cost",
                    problem: "Empty chairs cost money. Chasing deposits manually is awkward and time-consuming.",
                },
                {
                    label: "Distracted Artistry",
                    problem: "Stopping a precision cut or rinse to answer \"Are you open Monday?\" breaks your focus.",
                }
            ]}
            valueProps={[
                {
                    title: "Service Duration Logic",
                    description: "Ovela asks the right qualifying questions to ensure the correct time slot is booked for complex services.",
                    icon: <Clock className="w-5 h-5" />
                },
                {
                    title: "Deposit Enforcement",
                    description: "Politely informs clients of deposit policies during booking, ensuring commitment before they hang up.",
                    icon: <CreditCard className="w-5 h-5" />
                },
                {
                    title: "Squeeze-In Management",
                    description: "Handling \"Can you just squeeze me in?\" requests with firm, polite availability checks based on your real calendar.",
                    icon: <Scissors className="w-5 h-5" />
                }
            ]}
            workflowTitle="The Digital Front of House"
            workflowDescription="Like a trained salon coordinator, Ovela manages the flow of the book, protecting your time and maximizing daily revenue."
            ctaText="Upgrade Your Salon"
        />
    )
}
