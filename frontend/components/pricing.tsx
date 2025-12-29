"use client"

import { motion } from "framer-motion"
import { Check, Shield, Zap, Users } from "lucide-react"
import Link from "next/link"

export function Pricing() {
  return (
    <section id="pricing" className="py-32 px-6 bg-card relative overflow-hidden">
      {/* Background gradient for premium feel */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full h-full max-w-7xl opacity-30 pointer-events-none">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-primary/20 rounded-full blur-[100px]" />
        <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-accent/10 rounded-full blur-[100px]" />
      </div>

      <div className="max-w-4xl mx-auto relative z-10">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, ease: "easeOut" }}
          className="text-center mb-16"
        >
          <h2 className="font-serif text-4xl md:text-5xl tracking-tight mb-6">
            Simple, Transparent Pricing
          </h2>
          <p className="text-muted-foreground text-lg max-w-2xl mx-auto leading-relaxed">
            Our AI receptionist uses a straightforward two-part pricing structure.
            No hidden fees. No surprises.
          </p>
        </motion.div>

        {/* Pricing Structure Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-16">
          {/* One-Time Setup */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6, ease: "easeOut" }}
            className="p-8 rounded-3xl border border-border/50 bg-background/50 backdrop-blur-sm"
          >
            <div className="w-12 h-12 rounded-2xl bg-accent/10 flex items-center justify-center mb-6">
              <Zap className="w-6 h-6 text-accent" />
            </div>
            <h3 className="text-2xl font-serif mb-3">One-Time Setup Fee</h3>
            <p className="text-sm text-muted-foreground mb-6 leading-relaxed">
              A single onboarding payment that covers everything needed to get your AI receptionist live.
            </p>

            {/* 7-Day Trial Highlight */}
            <div className="mb-6 p-3 rounded-xl bg-accent/10 border border-accent/20">
              <p className="text-sm text-accent font-medium">✨ 7-Day Free Trial Included</p>
              <p className="text-xs text-muted-foreground mt-1">Test after setup. Cancel if not satisfied.</p>
            </div>

            <ul className="space-y-3">
              <li className="flex items-start gap-3">
                <Check className="w-4 h-4 text-accent mt-0.5 shrink-0" />
                <span className="text-sm text-foreground/80">Dedicated phone number setup</span>
              </li>
              <li className="flex items-start gap-3">
                <Check className="w-4 h-4 text-accent mt-0.5 shrink-0" />
                <span className="text-sm text-foreground/80">AI configuration for your business</span>
              </li>
              <li className="flex items-start gap-3">
                <Check className="w-4 h-4 text-accent mt-0.5 shrink-0" />
                <span className="text-sm text-foreground/80">Staff workflow alignment</span>
              </li>
              <li className="flex items-start gap-3">
                <Check className="w-4 h-4 text-accent mt-0.5 shrink-0" />
                <span className="text-sm text-foreground/80">Training & onboarding session</span>
              </li>
            </ul>
          </motion.div>

          {/* Monthly Subscription */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6, ease: "easeOut", delay: 0.15 }}
            className="p-8 rounded-3xl border border-primary/20 bg-primary/5 backdrop-blur-sm"
          >
            <div className="w-12 h-12 rounded-2xl bg-primary/10 flex items-center justify-center mb-6">
              <Users className="w-6 h-6 text-primary" />
            </div>
            <h3 className="text-2xl font-serif mb-3">Monthly Subscription</h3>
            <p className="text-sm text-muted-foreground mb-6 leading-relaxed">
              Ongoing monthly fee that keeps your AI receptionist running and improving.
            </p>

            <ul className="space-y-3">
              <li className="flex items-start gap-3">
                <Check className="w-4 h-4 text-primary mt-0.5 shrink-0" />
                <span className="text-sm text-foreground/80">Unlimited AI call handling</span>
              </li>
              <li className="flex items-start gap-3">
                <Check className="w-4 h-4 text-primary mt-0.5 shrink-0" />
                <span className="text-sm text-foreground/80">Booking & confirmation automation</span>
              </li>
              <li className="flex items-start gap-3">
                <Check className="w-4 h-4 text-primary mt-0.5 shrink-0" />
                <span className="text-sm text-foreground/80">System maintenance & updates</span>
              </li>
              <li className="flex items-start gap-3">
                <Check className="w-4 h-4 text-primary mt-0.5 shrink-0" />
                <span className="text-sm text-foreground/80">Ongoing improvements & support</span>
              </li>
            </ul>
          </motion.div>
        </div>

        {/* Pricing Depends On */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, ease: "easeOut", delay: 0.3 }}
          className="text-center mb-12"
        >
          <p className="text-muted-foreground text-sm mb-4">
            Your quote is tailored based on:
          </p>
          <div className="flex flex-wrap justify-center gap-3">
            <span className="px-4 py-2 rounded-full bg-secondary/50 text-sm text-foreground/80">
              Call volume
            </span>
            <span className="px-4 py-2 rounded-full bg-secondary/50 text-sm text-foreground/80">
              Business size
            </span>
            <span className="px-4 py-2 rounded-full bg-secondary/50 text-sm text-foreground/80">
              Required integrations
            </span>
          </div>
        </motion.div>

        {/* Trust Line + CTA */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, ease: "easeOut", delay: 0.4 }}
          className="text-center"
        >
          {/* Trust Statement */}
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-accent/10 text-accent text-sm font-medium mb-8 border border-accent/20">
            <Shield className="w-4 h-4" />
            <span>You'll know your exact costs before anything is charged</span>
          </div>

          {/* CTA */}
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <button
              onClick={() => {
                window.dispatchEvent(new CustomEvent("openDemoModal"))
                // Scroll to top so modal is visible
                window.scrollTo({ top: 0, behavior: "smooth" })
              }}
              className="px-8 py-4 rounded-full text-sm font-medium bg-primary text-primary-foreground hover:opacity-90 transition-all shadow-lg shadow-primary/20 cursor-pointer"
            >
              Try AI Demo
            </button>
            <Link
              href="#contact"
              className="px-8 py-4 rounded-full text-sm font-medium bg-secondary text-secondary-foreground hover:bg-secondary/80 transition-all"
            >
              Join Waitlist
            </Link>
          </div>

          {/* Footer Line */}
          <p className="mt-8 text-xs text-muted-foreground">
            Transparent pricing. No hidden fees. No lock-in.
          </p>
        </motion.div>
      </div>
    </section>
  )
}
