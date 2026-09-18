"use client"

import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Plus, Minus } from "lucide-react"

const faqs = [
  {
    q: "Is Ovela a business?",
    a: "No. Ovela is a personal engineering project. It runs in production on a real phone line, but it is not a registered business, has no customers, and has no pricing. Every call in its traces is a test call made by its author.",
  },
  {
    q: "How does it answer a call?",
    a: "The phone line streams audio to a Python backend. Deepgram Flux transcribes it and decides when the caller has finished speaking; an OpenAI model (gpt-4.1-nano) writes the reply, calling tools to check availability or look up a booking; Cartesia turns the reply into speech and streams it back while it is still being written.",
  },
  {
    q: "How fast does it respond?",
    a: "For a reply that needs no tool, the median time from the caller finishing to the first audio byte has been about 0.5–0.7 seconds on every day with enough calls to measure. A reply that has to check availability is slower — around 1.5–2.7 seconds — and that gap is the main open latency problem. The measurements, with sample sizes, are in the repository.",
  },
  {
    q: "Which booking software does it connect to?",
    a: "None yet. Availability and bookings go through a single adapter interface, so a property-management system can be plugged in without changing the call logic, but today the demo runs on its own booking store.",
  },
  {
    q: "What happens if a caller wants to speak to a person?",
    a: "The agent can transfer the call to a nominated number. The transfer is gated in code, not just in the prompt: it only dials once the caller has actually agreed to be put through.",
  },
  {
    q: "Can I see how it works?",
    a: "Yes — the code, the architecture and the measurements are on GitHub at github.com/My-CMDhub/Ovela-AI.",
  },
]

export function FAQ() {
  const [openIndex, setOpenIndex] = useState<number | null>(null)

  return (
    <section className="py-24 px-6 bg-background">
      {/* FAQPage structured data for Google rich results */}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify({
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": faqs.map(({ q, a }) => ({
              "@type": "Question",
              "name": q,
              "acceptedAnswer": {
                "@type": "Answer",
                "text": a
              }
            }))
          })
        }}
      />

      <div className="mx-auto max-w-3xl">
        {/* Header */}
        <div className="mb-14 text-center">
          <p className="text-sm font-medium uppercase tracking-widest text-muted-foreground mb-3">
            Common questions
          </p>
          <h2 className="text-3xl font-serif font-medium tracking-tight text-foreground sm:text-4xl">
            Questions people ask about this project
          </h2>
        </div>

        {/* Accordion */}
        <div className="divide-y divide-border">
          {faqs.map((faq, i) => {
            const isOpen = openIndex === i
            return (
              <div key={i}>
                <button
                  onClick={() => setOpenIndex(isOpen ? null : i)}
                  className="w-full flex items-center justify-between gap-6 py-5 text-left group"
                  aria-expanded={isOpen}
                >
                  <span className="text-base font-medium text-foreground group-hover:text-foreground/80 transition-colors">
                    {faq.q}
                  </span>
                  <span
                    className="shrink-0 flex items-center justify-center w-7 h-7 rounded-full border transition-colors duration-200"
                    style={{
                      borderColor: isOpen ? "var(--accent)" : "var(--border)",
                      color: isOpen ? "var(--accent)" : "var(--muted-foreground)"
                    }}
                  >
                    {isOpen ? <Minus className="w-3.5 h-3.5" /> : <Plus className="w-3.5 h-3.5" />}
                  </span>
                </button>

                <AnimatePresence initial={false}>
                  {isOpen && (
                    <motion.div
                      key="answer"
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
                      className="overflow-hidden"
                    >
                      <p className="pb-5 pr-12 text-base text-muted-foreground leading-relaxed">
                        {faq.a}
                      </p>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            )
          })}
        </div>
      </div>
    </section>
  )
}
