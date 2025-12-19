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
            What businesses say about Ovela
          </h2>
          <p className="text-muted-foreground text-base">
            Coming soon — early partners are onboarding now
          </p>
        </motion.div>

        {/* Placeholder Card */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, ease: "easeOut", delay: 0.2 }}
          className="relative p-12 bg-white dark:bg-black rounded-3xl border border-border/50 overflow-hidden"
        >
          {/* Subtle background pattern */}
          <div className="absolute inset-0 opacity-[0.02] dark:opacity-[0.05]">
            <div className="absolute inset-0" style={{
              backgroundImage: `radial-gradient(circle at 2px 2px, currentColor 1px, transparent 0)`,
              backgroundSize: '32px 32px'
            }} />
          </div>

          <div className="relative z-10 text-center max-w-2xl mx-auto">
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-zinc-100 dark:bg-zinc-900 text-zinc-600 dark:text-zinc-400 text-sm font-medium mb-8">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-zinc-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-zinc-500"></span>
              </span>
              Currently onboarding our first partners
            </div>

            <p className="text-lg text-muted-foreground leading-relaxed mb-12">
              We're currently onboarding our first group of service businesses.
              <br />
              Their real experiences will be published here soon.
            </p>

            {/* Founder Vision */}
            <div className="pt-12 border-t border-border/50">
              <div className="flex items-start gap-4 text-left">
                <div className="flex-shrink-0 w-12 h-12 rounded-full bg-gradient-to-br from-zinc-900 to-zinc-700 dark:from-zinc-100 dark:to-zinc-300 flex items-center justify-center text-white dark:text-black font-serif text-xl font-bold">
                  O
                </div>
                <div className="flex-1">
                  <p className="text-sm font-medium text-muted-foreground mb-3">Vision from the founder</p>
                  <blockquote className="text-lg md:text-xl font-serif italic text-foreground leading-relaxed">
                    "My goal with Ovela is simple: Let every missed call become a booked customer, so you can focus on what you do best."
                  </blockquote>
                  <p className="text-sm text-muted-foreground mt-4">
                    — Ovela Team
                  </p>
                </div>
              </div>
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
            Join the waitlist to be among the first businesses to experience Ovela
          </p>
        </motion.div>
      </div>
    </section>
  )
}
