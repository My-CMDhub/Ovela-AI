"use client"

import { motion } from "framer-motion"

export function Testimonials() {
  return (
    <section className="py-32 px-6 bg-zinc-50 dark:bg-zinc-950">
      <div className="max-w-4xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, ease: "easeOut" }}
          className="text-center mb-16"
        >
          <h2 className="font-serif text-4xl md:text-5xl tracking-tight mb-4">
            Built for the businesses actually accepting calls right now
          </h2>
          <p className="text-muted-foreground text-base">
            Founding cohort — we’re onboarding our first group of businesses in Australia
          </p>
        </motion.div>

        {/* Founding Cohort Card */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, ease: "easeOut", delay: 0.2 }}
          className="relative p-10 sm:p-12 bg-white dark:bg-black rounded-3xl border border-border/50 overflow-hidden mb-8"
        >
          <div className="absolute inset-0 opacity-[0.02] dark:opacity-[0.05]">
            <div className="absolute inset-0" style={{
              backgroundImage: `radial-gradient(circle at 2px 2px, currentColor 1px, transparent 0)`,
              backgroundSize: '32px 32px'
            }} />
          </div>

          <div className="relative z-10 max-w-2xl mx-auto">
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary/5 text-primary text-sm font-medium border border-primary/20 mb-8">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-primary"></span>
              </span>
              Founding Cohort — Limited Spots Available
            </div>

            <p className="text-lg text-muted-foreground leading-relaxed mb-8">
              We&apos;re accepting our first cohort of businesses across hospitality, trades, and service industries in Australia. Founding members get:
            </p>

            <ul className="space-y-4 mb-10">
              <li className="flex items-start gap-3">
                <span className="w-5 h-5 rounded-full bg-primary/10 text-primary flex items-center justify-center text-xs font-bold shrink-0 mt-0.5">✓</span>
                <span className="text-foreground/80"><strong className="text-foreground">Direct founder involvement</strong> in your setup — not a support ticket queue</span>
              </li>
              <li className="flex items-start gap-3">
                <span className="w-5 h-5 rounded-full bg-primary/10 text-primary flex items-center justify-center text-xs font-bold shrink-0 mt-0.5">✓</span>
                <span className="text-foreground/80"><strong className="text-foreground">Founding pricing locked in</strong> — AUD $300 setup, AUD $200/month. This won&apos;t stay this low.</span>
              </li>
              <li className="flex items-start gap-3">
                <span className="w-5 h-5 rounded-full bg-primary/10 text-primary flex items-center justify-center text-xs font-bold shrink-0 mt-0.5">✓</span>
                <span className="text-foreground/80"><strong className="text-foreground">Input on the product</strong> — your feedback directly shapes how Ovela develops</span>
              </li>
              <li className="flex items-start gap-3">
                <span className="w-5 h-5 rounded-full bg-primary/10 text-primary flex items-center justify-center text-xs font-bold shrink-0 mt-0.5">✓</span>
                <span className="text-foreground/80"><strong className="text-foreground">21-day free trial</strong> — see your exact monthly cost from real usage before you&apos;re charged anything</span>
              </li>
            </ul>

            <p className="text-sm text-muted-foreground italic">Spots are limited. We onboard manually and give each business proper attention.</p>
          </div>
        </motion.div>

        {/* Founder Vision */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, ease: "easeOut", delay: 0.3 }}
          className="p-10 bg-white dark:bg-black rounded-3xl border border-border/50"
        >
          <div className="flex items-start gap-4">
            <div className="flex-shrink-0 w-12 h-12 rounded-full bg-gradient-to-br from-zinc-900 to-zinc-700 dark:from-zinc-100 dark:to-zinc-300 flex items-center justify-center text-white dark:text-black font-serif text-xl font-bold">
              O
            </div>
            <div className="flex-1">
              <p className="text-sm font-medium text-muted-foreground mb-3">From the founder</p>
              <blockquote className="text-lg md:text-xl font-serif italic text-foreground leading-relaxed">
                "We built Ovela because businesses shouldn't have to choose between being on the job and being available to customers. Every missed call is a missed booking. We fix that."
              </blockquote>
              <p className="text-sm text-muted-foreground mt-4">
                — Ovela Team
              </p>
            </div>
          </div>
        </motion.div>

        {/* Trust indicators */}
        <motion.div
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 0.8, delay: 0.4 }}
          className="mt-12 text-center"
        >
          <p className="text-sm text-muted-foreground">
            Accepting a limited number of early access businesses — <span className="text-foreground font-medium">no lock-in, 21-day free trial included</span>
          </p>
        </motion.div>
      </div>
    </section>
  )
}
