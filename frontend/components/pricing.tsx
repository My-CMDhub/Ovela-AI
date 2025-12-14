"use client"

import { motion } from "framer-motion"
import { Check } from "lucide-react"
import Link from "next/link"

const plans = [
  {
    name: "Starter",
    description: "Perfect for solo studios",
    features: [
      "Unlimited WhatsApp bookings",
      "Automated confirmations",
      "Service & price auto-replies",
      "Daily booking summary",
      "1 staff calendar",
    ],
  },
  {
    name: "Pro",
    description: "For growing multi-branch studios",
    features: [
      "Everything in Starter",
      "Multiple staff calendars",
      "Multi-location support",
      "Priority support",
      "Advanced analytics",
      "Custom AI responses",
    ],
    featured: true,
  },
]

export function Pricing() {
  return (
    <section id="pricing" className="py-32 px-6 bg-card relative overflow-hidden">
      {/* Background gradient for premium feel */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full h-full max-w-7xl opacity-30 pointer-events-none">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-primary/20 rounded-full blur-[100px]" />
        <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-accent/10 rounded-full blur-[100px]" />
      </div>

      <div className="max-w-4xl mx-auto relative z-10">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, ease: "easeOut" }}
          className="text-center mb-20"
        >
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-accent/10 text-accent text-xs font-medium tracking-wider uppercase mb-6 border border-accent/20">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-accent"></span>
            </span>
            Limited Intake
          </div>
          <h2 className="font-serif text-4xl md:text-5xl tracking-tight mb-6">Exclusive Pilot Program</h2>
          <p className="text-muted-foreground text-lg max-w-2xl mx-auto leading-relaxed">
            Experience the power of Ovela AI with <strong className="text-foreground">zero risk</strong>. We are onboarding a limited number of founding partners this month to ensure maximum success.
          </p>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          {/* Standard Access */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6, ease: "easeOut" }}
            className="p-8 rounded-3xl border border-border/50 bg-background/50 backdrop-blur-sm hover:border-border transition-colors duration-300"
          >
            <h3 className="text-2xl font-serif mb-2">Standard Access</h3>
            <p className="text-sm text-muted-foreground mb-8">Perfect for solo studios ready to automate.</p>

            <ul className="space-y-4 mb-10">
              <li className="flex items-center gap-3">
                <div className="w-5 h-5 rounded-full bg-accent/10 flex items-center justify-center shrink-0">
                  <Check className="w-3 h-3 text-accent" />
                </div>
                <span className="text-sm font-medium text-foreground">30-Day Performance Pilot (No Cost)</span>
              </li>
              <li className="flex items-center gap-3">
                <Check className="w-4 h-4 text-muted-foreground" />
                <span className="text-sm text-muted-foreground">Unlimited WhatsApp bookings</span>
              </li>
              <li className="flex items-center gap-3">
                <Check className="w-4 h-4 text-muted-foreground" />
                <span className="text-sm text-muted-foreground">White-Glove Setup Included</span>
              </li>
              <li className="flex items-center gap-3">
                <Check className="w-4 h-4 text-muted-foreground" />
                <span className="text-sm text-muted-foreground">Daily booking summary</span>
              </li>
            </ul>

            <Link
              href="#contact"
              className="block text-center py-4 rounded-full text-sm font-medium bg-secondary text-secondary-foreground hover:bg-secondary/80 transition-all"
            >
              Request Invitation
            </Link>
          </motion.div>

          {/* Priority Access */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6, ease: "easeOut", delay: 0.2 }}
            className="relative p-8 rounded-3xl border border-primary/20 bg-primary/5 backdrop-blur-sm"
          >
            <div className="absolute -top-4 left-1/2 -translate-x-1/2 px-4 py-1 bg-primary text-primary-foreground text-xs font-bold uppercase tracking-wider rounded-full shadow-lg">
              Founding Partner Slot
            </div>

            <h3 className="text-2xl font-serif mb-2">Priority Access</h3>
            <p className="text-sm text-muted-foreground mb-8">For growing studios requiring dedicated support.</p>

            <ul className="space-y-4 mb-10">
              <li className="flex items-center gap-3">
                <div className="w-5 h-5 rounded-full bg-primary/20 flex items-center justify-center shrink-0">
                  <Check className="w-3 h-3 text-primary" />
                </div>
                <span className="text-sm font-medium text-foreground">Priority Onboarding Slot</span>
              </li>
              <li className="flex items-center gap-3">
                <div className="w-5 h-5 rounded-full bg-primary/20 flex items-center justify-center shrink-0">
                  <Check className="w-3 h-3 text-primary" />
                </div>
                <span className="text-sm font-medium text-foreground">Dedicated Success Manager</span>
              </li>
              <li className="flex items-center gap-3">
                <Check className="w-4 h-4 text-muted-foreground" />
                <span className="text-sm text-muted-foreground">Multi-location support</span>
              </li>
              <li className="flex items-center gap-3">
                <Check className="w-4 h-4 text-muted-foreground" />
                <span className="text-sm text-muted-foreground">Custom AI responses</span>
              </li>
            </ul>

            <Link
              href="#contact"
              className="block text-center py-4 rounded-full text-sm font-medium bg-primary text-primary-foreground hover:opacity-90 transition-all shadow-lg shadow-primary/20"
            >
              Request Invitation
            </Link>
          </motion.div>
        </div>
      </div>
    </section>
  )
}
