"use client"

import { motion } from "framer-motion"
import { Phone, RefreshCw, Database, Clock, Brain, Settings, BarChart3 } from "lucide-react"
import { FeaturesFolderAnimation, type FeatureCardData } from "./features-folder-animation"

const features: FeatureCardData[] = [
  {
    icon: Phone,
    title: "AI Voice Answering",
    description: "Natural conversations that sound human. Answers calls 24/7 in your brand voice.",
  },
  {
    icon: Database,
    title: "Works With Your Systems",
    description: "Integrates with your existing booking and management tools. No forced migration.",
  },
  {
    icon: Clock,
    title: "Real-Time Booking",
    description: "Checks live availability and books appointments during the call. No delays.",
  },
  {
    icon: RefreshCw,
    title: "Reschedule & Cancel",
    description: "Customers call to change appointments. Ovela handles it seamlessly.",
  },
  {
    icon: Brain,
    title: "Smart Call Routing",
    description: "Complex queries get forwarded to you. Routine calls handled automatically.",
  },
  {
    icon: Settings,
    title: "Easy Setup",
    description: "30 minutes to go live. No technical skills required. We handle the rest.",
  },
  {
    icon: BarChart3,
    title: "Call Analytics",
    description: "See every call, booking, and missed opportunity in your dashboard.",
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
          <h2 className="font-serif text-4xl md:text-5xl tracking-tight mb-4">Everything you need</h2>
          <p className="text-muted-foreground text-lg max-w-xl mx-auto">
            A complete AI receptionist that works while you focus on your craft.
          </p>
        </motion.div>
      </div>

      {/* Folder Animation Container */}
      <FeaturesFolderAnimation features={features} folderColor="#D8B4FE" />
    </section>
  )
}
