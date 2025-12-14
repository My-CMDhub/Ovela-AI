"use client"

import { motion } from "framer-motion"
import { CalendarCheck, RefreshCw, List, Clock, User, Settings, BarChart3 } from "lucide-react"

const features = [
  {
    icon: CalendarCheck,
    title: "Smart WhatsApp Booking",
    description: "Clients book appointments directly via WhatsApp with natural conversation.",
  },
  {
    icon: RefreshCw,
    title: "Reschedule & Cancel",
    description: "One message to change or cancel — Ovela handles it seamlessly.",
  },
  {
    icon: List,
    title: "Service & Price Auto-Replies",
    description: "Instant answers about services, pricing, and availability.",
  },
  {
    icon: Clock,
    title: "Auto Slot Checking",
    description: "No double bookings ever. Real-time calendar sync.",
  },
  {
    icon: User,
    title: "Business Profile Memory",
    description: "Ovela remembers client preferences and booking history.",
  },
  {
    icon: Settings,
    title: "Owner Admin Commands",
    description: "Full control via simple commands. Block times, adjust settings.",
  },
  {
    icon: BarChart3,
    title: "Analytics & Summaries",
    description: "Daily booking summaries and insights delivered to you.",
  },
]

export function Features() {
  return (
    <section id="features" className="py-32 px-6">
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

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((feature, index) => (
            <motion.div
              key={index}
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6, ease: "easeOut", delay: index * 0.1 }}
              whileHover={{ y: -4 }}
              className="group p-8 bg-card rounded-2xl border border-border/50 hover:border-border hover:shadow-lg hover:shadow-muted/50 transition-all duration-300"
            >
              <motion.div
                whileHover={{ scale: 1.05 }}
                transition={{ duration: 0.2 }}
                className="w-12 h-12 rounded-xl bg-muted flex items-center justify-center mb-6 group-hover:bg-accent/30 transition-colors"
              >
                <feature.icon className="w-5 h-5 text-foreground" />
              </motion.div>
              <h3 className="text-lg font-medium mb-2">{feature.title}</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">{feature.description}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  )
}
