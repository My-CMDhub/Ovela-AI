"use client"

import { motion } from "framer-motion"
import { Phone, RefreshCw, Database, Clock, Brain, Settings, BarChart3 } from "lucide-react"
import { FeaturesFolderAnimation, type FeatureCardData } from "./features-folder-animation"

const features: FeatureCardData[] = [
  {
    icon: Phone,
    title: "Answers Every Call",
    description: "Every call gets picked up, every time. No voicemails. No missed customers. Your business sounds professional 24/7.",
  },
  {
    icon: Database,
    title: "Booking Data Behind an Adapter",
    description: "Availability and bookings go through one adapter interface, so a property-management system can be swapped in without touching the call logic. Today it runs on its own booking store — no third-party system is connected.",
  },
  {
    icon: Clock,
    title: "Books Jobs Live During the Call",
    description: "Checks real-time availability and creates the booking before the caller hangs up. No callbacks needed.",
  },
  {
    icon: RefreshCw,
    title: "Handles Reschedules & Cancellations",
    description: "When customers call to change their appointment, Ovela takes care of it without pulling you away from the job.",
  },
  {
    icon: Brain,
    title: "Passes the Right Calls to You",
    description: "Routine calls are handled automatically. Anything that genuinely needs a human gets transferred straight to your team.",
  },
  {
    icon: Settings,
    title: "We Handle the Entire Setup",
    description: "No technical work required on your end. We configure everything, connect your systems, and get you live. You don't touch a setting.",
  },
  {
    icon: BarChart3,
    title: "See Every Call & Booking",
    description: "Your dashboard shows every call handled, booking made, and opportunity captured — all in one place.",
  },
]

export function Features() {
  return (
    <section id="features" className="px-6 pt-32 pb-32">
      <div className="max-w-6xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, ease: "easeOut" }}
          className="text-center mb-20"
        >
          <h2 className="font-serif text-4xl md:text-5xl tracking-tight mb-4 text-balance">Call handling infrastructure for modern service businesses</h2>
          <p className="text-muted-foreground text-lg max-w-xl mx-auto text-balance">
            Every inbound call — hotel inquiry, trade job, clinic appointment handled automatically and synced with your systems.
          </p>
        </motion.div>
      </div>

      {/* Folder Animation Container */}
      <FeaturesFolderAnimation features={features} folderColor="#D8B4FE" />
    </section>
  )
}
