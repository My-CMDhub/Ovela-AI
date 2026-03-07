"use client"

import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Plus, Minus } from "lucide-react"

const faqs = [
  {
    q: "How does Ovela answer my calls?",
    a: "When a customer calls your business number, Ovela answers in your business name, understands the reason for the call, and responds naturally. If they want to book a job or reservation, Ovela checks your live availability and creates the booking directly in your existing software — with no human involved. You receive a summary of every call."
  },
  {
    q: "How much does an AI receptionist cost in Australia?",
    a: "There is a one-time setup fee of AUD $300, which covers full configuration and software integration. The monthly fee is AUD $200. You trial Ovela free for 21 days first — your exact monthly cost is confirmed from real call data before anything is charged."
  },
  {
    q: "Which booking software does Ovela connect to?",
    a: "Ovela integrates directly with ServiceM8, Tradify, Cliniko, RMS Cloud, Fergus, Xero, Halaxy, Apaleo, Zoho CRM, Vagaro, and CloudBeds. If you use a different system, get in touch — we are actively expanding integrations."
  },
  {
    q: "What happens if a caller needs to speak to a real person?",
    a: "Ovela recognises when a caller needs a human — for complaints, urgent situations, or when they specifically ask to be transferred. It connects the call to your nominated staff member and sends an SMS with call context so they are briefed before they answer."
  },
  {
    q: "Does Ovela answer calls after hours and on weekends?",
    a: "Yes. Ovela answers every call 24 hours a day, 7 days a week — including weekends and public holidays — at no extra charge. Most businesses see the biggest impact overnight and on weekends, when missed calls previously meant missed bookings."
  },
  {
    q: "Do I need to change my existing phone number?",
    a: "No. Your current business number stays exactly the same. Ovela works alongside your existing setup without disruption. If you want to take a call yourself, Ovela steps aside."
  },
  {
    q: "How long does setup take?",
    a: "We handle the entire setup for you — you don't touch a single setting. After your onboarding call, it typically takes a few business days to configure and test your integration. You approve everything before going live."
  }
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
            Questions business owners ask
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
