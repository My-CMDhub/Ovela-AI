"use client"

import React from "react"
import { motion, AnimatePresence } from "framer-motion"
import { useState, useEffect } from "react"
import { PhoneCall } from "@/components/animate-ui/icons/phone-call"
import { Sparkles } from "@/components/animate-ui/icons/sparkles"
import { ClipboardList } from "@/components/animate-ui/icons/clipboard-list"
import { CircleCheckBig } from "@/components/animate-ui/icons/circle-check-big"
import { Check, CreditCard, Workflow, ShieldCheck } from "lucide-react"

const painPoints = [
  {
    icon: (
      <svg viewBox="0 0 24 24" fill="none" className="w-6 h-6" stroke="currentColor" strokeWidth="1.5">
        <circle cx="12" cy="12" r="10" />
        <path d="M12 6v6l4 2" />
      </svg>
    ),
    title: "Endless Waiting",
    description: "Your clients hate waiting for responses",
    stat: "67%",
    statLabel: "clients abandon slow responders",
  },
  {
    icon: (
      <svg viewBox="0 0 24 24" fill="none" className="w-6 h-6" stroke="currentColor" strokeWidth="1.5">
        <path d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
      </svg>
    ),
    title: "Repetitive Messages",
    description: "Same questions, every single day",
    stat: "40+",
    statLabel: "messages answered daily",
  },
  {
    icon: (
      <svg viewBox="0 0 24 24" fill="none" className="w-6 h-6" stroke="currentColor" strokeWidth="1.5">
        <path d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
    title: "Lost Revenue",
    description: "Missed bookings = money left on table",
    stat: "$2.4k",
    statLabel: "average monthly loss",
  },
]

// Solution steps with animate-ui icons and mockups
const solutionSteps = [
  {
    step: 1,
    title: "Incoming Call",
    description: "Instant answer, every time",
    detail: "< 2 sec",
    detailLabel: "response time",
    Icon: PhoneCall,
    mockup: (isActive: boolean) => (
      <div className="w-full max-w-sm mx-auto p-4 rounded-xl bg-background border border-border shadow-lg" key={isActive ? "active" : "inactive"}>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-green-500/10 flex items-center justify-center text-green-500">
              <PhoneCall size={20} />
            </div>
            <div>
              <div className="text-sm font-medium">Incoming Call</div>
              <div className="text-xs text-muted-foreground">+61 400 123 456</div>
            </div>
          </div>
          <motion.div
            animate={{ scale: [1, 1.2, 1], opacity: [0.5, 1, 0.5] }}
            transition={{ duration: 1.5, repeat: Infinity }}
            className="w-2 h-2 rounded-full bg-green-500"
          />
        </div>

        {isActive && (
          <div className="bg-muted/30 rounded-lg p-3 space-y-2">
            <div className="flex gap-2">
              <div className="w-1 h-8 rounded-full bg-accent/30" />
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.3, delay: 0.2 }}
                className="text-sm font-medium leading-relaxed"
              >
                <motion.span
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ duration: 1.5, delay: 0.4 }}
                  className="inline-block max-w-[240px] sm:max-w-full break-words"
                >
                  "Hi, do you have a room for 2 people on the 24th?"
                </motion.span>
              </motion.div>
            </div>
          </div>
        )}
      </div>
    ),
  },
  {
    step: 2,
    title: "AI Understanding",
    description: "Natural conversation intelligence",
    detail: "100%",
    detailLabel: "context aware",
    Icon: Sparkles,
    mockup: (isActive: boolean) => (
      <div className="w-full max-w-sm mx-auto p-4 rounded-xl bg-background border border-border shadow-lg" key={isActive ? "active" : "inactive"}>
        <div className="flex items-center gap-2 mb-4">
          <Sparkles className="text-accent w-4 h-4" />
          <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Intent Extraction</span>
        </div>

        {/* Context Cards */}
        <div className="space-y-2">
          {[
            { label: "Intent", value: "New Booking", color: "text-blue-500 bg-blue-500/10" },
            { label: "Date", value: "Oct 24", color: "text-purple-500 bg-purple-500/10" },
            { label: "Guests", value: "2 Adults", color: "text-orange-500 bg-orange-500/10" }
          ].map((item, i) => (
            <motion.div
              key={item.label}
              initial={{ opacity: 0, x: -10 }}
              animate={isActive ? { opacity: 1, x: 0 } : { opacity: 0, x: -10 }}
              transition={{ delay: isActive ? 0.3 + i * 0.2 : 0, duration: 0.4 }}
              className="flex items-center justify-between p-2 rounded-lg bg-muted/20 border border-border/50"
            >
              <span className="text-xs text-muted-foreground">{item.label}</span>
              <span className={`text-xs font-medium px-2 py-0.5 rounded ${item.color}`}>
                {item.value}
              </span>
            </motion.div>
          ))}
        </div>
      </div>
    ),
  },
  {
    step: 3,
    title: "System Sync",
    description: "Real-time availability check",
    detail: "Live",
    detailLabel: "calendar + CRM",
    Icon: ClipboardList,
    mockup: (isActive: boolean) => (
      <div className="w-full max-w-md mx-auto p-4 rounded-xl bg-background border border-border shadow-lg" key={isActive ? "active" : "inactive"}>
        <div className="flex items-center justify-between mb-4 border-b border-border/50 pb-2">
          <span className="text-xs font-medium text-muted-foreground">Availability Scan</span>
          <div className="flex gap-1">
            <div className="w-2 h-2 rounded-full bg-red-400" />
            <div className="w-2 h-2 rounded-full bg-yellow-400" />
            <div className="w-2 h-2 rounded-full bg-green-400" />
          </div>
        </div>

        {/* Calendar Date Scanning Animation */}
        <div className="grid grid-cols-4 gap-2">
          {[
            { date: "Oct 22", status: "booked" },
            { date: "Oct 23", status: "booked" },
            { date: "Oct 24", status: "available" }, // Target
            { date: "Oct 25", status: "available" },
          ].map((slot, i) => (
            <motion.div
              key={i}
              animate={isActive ? {
                scale: slot.date === "Oct 24" ? [1, 1.1, 1] : 1,
                borderColor: slot.date === "Oct 24" ? ["transparent", "hsl(var(--accent))", "hsl(var(--accent))"] : "transparent",
                backgroundColor: slot.date === "Oct 24" ? ["transparent", "hsl(var(--accent) / 0.1)", "hsl(var(--accent) / 0.1)"] : "transparent"
              } : {}}
              transition={{
                scale: { delay: 1.5, duration: 0.4 },
                borderColor: { delay: 1.5, duration: 0.4 },
                backgroundColor: { delay: 1.5, duration: 0.4 }
              }}
              className="relative overflow-hidden flex flex-col items-center justify-center p-3 rounded border border-transparent transition-colors"
            >
              {/* Scanning beam effect */}
              {isActive && (
                <motion.div
                  initial={{ top: "-100%" }}
                  animate={{ top: "200%" }}
                  transition={{ duration: 1, delay: i * 0.2, ease: "linear" }}
                  className="absolute left-0 right-0 h-1/2 bg-gradient-to-b from-transparent via-accent/10 to-transparent pointer-events-none"
                />
              )}

              <span className="text-[10px] text-muted-foreground uppercase tracking-wide">{slot.date}</span>
              <span className={`text-xs font-bold mt-1 ${slot.status === "available" ? "text-foreground" : "text-muted-foreground/50 line-through"
                }`}>
                {slot.status === "booked" ? "Booked" : "Open"}
              </span>

              {/* Selection Check for Oct 24 */}
              {slot.date === "Oct 24" && isActive && (
                <motion.div
                  initial={{ opacity: 0, scale: 0 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: 1.8, type: "spring" }}
                  className="absolute -top-1 -right-1 w-4 h-4 bg-accent rounded-full flex items-center justify-center"
                >
                  <Check size={10} className="text-white" />
                </motion.div>
              )}
            </motion.div>
          ))}
        </div>

        <div className="mt-3 text-center">
          {isActive && (
            <motion.div
              initial={{ opacity: 0, y: 5 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 2.0 }}
              className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-accent/10 border border-accent/20 text-[10px] font-medium text-accent"
            >
              <Check size={10} />
              Availability Confirmed
            </motion.div>
          )}
        </div>
      </div>
    ),
  },
  {
    step: 4,
    title: "Booking Confirmed",
    description: "Appointment locked & notified",
    detail: "Auto",
    detailLabel: "SMS + calendar",
    Icon: CircleCheckBig,
    mockup: (isActive: boolean) => (
      <div className="w-full max-w-sm mx-auto" key={isActive ? "active" : "inactive"}>
        <motion.div
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          className="bg-background border border-green-500/20 shadow-xl shadow-green-500/5 rounded-2xl p-6 text-center"
        >
          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ type: "spring", stiffness: 200, delay: 0.2 }}
            className="w-16 h-16 mx-auto bg-green-500 rounded-full flex items-center justify-center mb-4 text-white shadow-lg shadow-green-500/30"
          >
            <Check className="w-8 h-8" strokeWidth={3} />
          </motion.div>

          <h4 className="text-lg font-semibold mb-1">Booking Confirmed</h4>
          <p className="text-sm text-muted-foreground mb-4">Confirmation sent to guest.</p>

          <motion.div
            initial={{ y: 10, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.5 }}
            className="bg-muted/40 rounded-xl p-4 text-left border border-border/50"
          >
            <div className="flex gap-3 items-start">
              <div className="w-8 h-8 rounded-full bg-blue-500/10 flex items-center justify-center shrink-0">
                <span className="text-[10px] font-bold text-blue-500">SMS</span>
              </div>
              <div className="space-y-1">
                <p className="text-xs text-foreground font-medium">Ovela Motel</p>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  Hi! Your booking for <span className="text-foreground font-medium">Oct 24</span> is confirmed. Check-in is at 2pm. Reply HELP for info.
                </p>
              </div>
            </div>
          </motion.div>
        </motion.div>
      </div>
    ),
  },
]

export function ProblemSolution() {
  const [activePain, setActivePain] = useState(0)
  const [activeStep, setActiveStep] = useState(0)

  // Cycle pain points
  useEffect(() => {
    const interval = setInterval(() => {
      setActivePain((prev) => (prev + 1) % painPoints.length)
    }, 3000)
    return () => clearInterval(interval)
  }, [])

  // Cycle solution steps
  useEffect(() => {
    const interval = setInterval(() => {
      setActiveStep((prev) => (prev + 1) % solutionSteps.length)
    }, 3500)
    return () => clearInterval(interval)
  }, [])

  return (
    <section className="py-16 md:py-32 px-6 bg-card overflow-hidden">
      <div className="max-w-6xl mx-auto">
        {/* Pain Points */}
        <div className="mb-32">
          <p className="text-sm text-muted-foreground uppercase tracking-[0.2em] mb-4 text-center">The Problem</p>

          <motion.p
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="font-serif text-4xl md:text-5xl text-center mb-16 text-balance"
          >
            Stop Losing Appointments
            <br />
            <span className="italic">to Missed Calls</span>
          </motion.p>

          <div className="grid md:grid-cols-3 gap-6">
            {painPoints.map((pain, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.6, delay: index * 0.15 }}
                onMouseEnter={() => setActivePain(index)}
                className="group relative"
              >
                <div
                  className={`relative bg-background border rounded-2xl p-8 transition-all duration-500 overflow-hidden ${activePain === index ? "border-accent shadow-lg shadow-accent/10" : "border-border/50"
                    }`}
                >
                  <motion.div
                    animate={{ scale: activePain === index ? 1.1 : 1 }}
                    transition={{ duration: 0.3 }}
                    className={`w-14 h-14 rounded-2xl flex items-center justify-center mb-6 transition-colors duration-300 ${activePain === index ? "bg-accent/20 text-foreground" : "bg-muted text-muted-foreground"
                      }`}
                  >
                    {pain.icon}
                  </motion.div>

                  <h3 className="font-serif text-2xl mb-2">{pain.title}</h3>
                  <p className="text-muted-foreground mb-6">{pain.description}</p>

                  <div className="pt-6 border-t border-border/30">
                    <div className="flex items-end gap-2">
                      <motion.span
                        animate={{ opacity: activePain === index ? 1 : 0.5 }}
                        className="font-serif text-4xl text-accent"
                      >
                        {pain.stat}
                      </motion.span>
                      <span className="text-sm text-muted-foreground mb-1">{pain.statLabel}</span>
                    </div>
                  </div>

                  <AnimatePresence>
                    {activePain === index && (
                      <motion.div
                        initial={{ scaleX: 0 }}
                        animate={{ scaleX: 1 }}
                        exit={{ scaleX: 0 }}
                        transition={{ duration: 3, ease: "easeOut" }}
                        className="absolute bottom-0 left-0 right-0 h-[2px] bg-accent origin-left"
                        style={{ borderBottomLeftRadius: "1rem", borderBottomRightRadius: "1rem" }}
                      />
                    )}
                  </AnimatePresence>
                </div>
              </motion.div>
            ))}
          </div>
        </div>

        {/* Solution Section */}
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.8 }}
        >
          <p className="text-sm text-muted-foreground uppercase tracking-[0.2em] mb-4 text-center">The Solution</p>
          <h2 className="font-serif text-4xl md:text-5xl text-center mb-6 text-balance">
            From Ring to Booking
            <br />
            <span className="italic">In Seconds</span>
          </h2>
          <p className="text-center text-muted-foreground max-w-xl mx-auto mb-16">
            Ovela handles every call with natural conversation, turning inquiries into confirmed appointments.
          </p>

          {/* Desktop: Premium Cinema Layout */}
          <div className="hidden md:block">
            {/* Step Indicators */}
            <div className="grid grid-cols-4 gap-4 mb-12">
              {solutionSteps.map((item, index) => (
                <div
                  key={item.step}
                  onMouseEnter={() => setActiveStep(index)}
                  className="cursor-pointer group"
                >
                  <div className={`h-[2px] w-full rounded-full mb-6 transition-all duration-500 ${activeStep === index
                    ? "bg-accent"
                    : activeStep > index
                      ? "bg-accent/50"
                      : "bg-border"
                    }`} />

                  <div className={`flex items-start gap-4 transition-opacity duration-300 ${activeStep === index ? "opacity-100" : "opacity-40 hover:opacity-70"
                    }`}>
                    <div className={`p-3 rounded-xl transition-colors duration-300 ${activeStep === index ? "bg-accent/10 text-accent" : "bg-muted text-muted-foreground"
                      }`}>
                      <item.Icon size={24} />
                    </div>
                    <div>
                      <h3 className="font-serif text-lg mb-1">{item.title}</h3>
                      <p className="text-sm text-muted-foreground leading-snug">{item.description}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* Main Visual Stage */}
            <div className="relative rounded-3xl border border-border/40 bg-gradient-to-br from-background/50 to-muted/20 overflow-hidden backdrop-blur-sm h-[400px] shadow-2xl shadow-black/5 dark:shadow-black/20 dark:border-white/10">
              {/* Grid Background - Visible in both modes */}
              <div className="absolute inset-0 bg-grid-black/[0.02] dark:bg-grid-white/[0.02]" />

              <AnimatePresence mode="wait">
                <motion.div
                  key={activeStep}
                  initial={{ opacity: 0, scale: 0.98, filter: "blur(4px)" }}
                  animate={{ opacity: 1, scale: 1, filter: "blur(0px)" }}
                  exit={{ opacity: 0, scale: 1.02, filter: "blur(4px)" }}
                  transition={{ duration: 0.4, ease: "easeOut" }}
                  className="absolute inset-0 flex items-center justify-center p-8 sm:p-12"
                >
                  <div className="w-full max-w-lg transform-gpu">
                    {solutionSteps[activeStep].mockup(true)}
                  </div>
                </motion.div>
              </AnimatePresence>

              {/* Formatting the detail/stat for the stage */}
              <div className="absolute bottom-6 right-6 flex items-end gap-3 px-5 py-2.5 rounded-full bg-background/80 border border-border/50 backdrop-blur-md shadow-sm">
                <span className="font-serif text-2xl text-accent">
                  {solutionSteps[activeStep].detail}
                </span>
                <span className="text-[10px] text-muted-foreground mb-1.5 uppercase tracking-wider font-medium">
                  {solutionSteps[activeStep].detailLabel}
                </span>
              </div>
            </div>
          </div>

          {/* Mobile: Clean Vertical Timeline */}
          <div className="md:hidden space-y-8 pl-4 border-l-2 border-border/30 ml-4">
            {solutionSteps.map((item, index) => (
              <div key={item.step} className="relative pl-8">
                {/* Timeline dot */}
                <div className={`absolute -left-[1.2rem] top-0 w-8 h-8 rounded-full border-4 border-background flex items-center justify-center transition-colors ${activeStep === index ? "bg-accent text-accent-foreground" : "bg-muted text-muted-foreground"
                  }`}>
                  <span className="text-[10px] font-bold">{item.step}</span>
                </div>

                <div className="mb-4">
                  <h3 className="font-serif text-xl mb-1">{item.title}</h3>
                  <p className="text-sm text-muted-foreground">{item.description}</p>
                </div>

                <div className={`rounded-xl border transition-all duration-500 ${activeStep === index
                  ? "bg-accent/5 border-accent/20 shadow-lg shadow-accent/5"
                  : "bg-muted/20 border-white/5 opacity-70"
                  } p-6 mb-4`}>
                  {item.mockup(activeStep === index)}
                </div>
              </div>
            ))}
          </div>
        </motion.div>

        {/* Orchestrator / Capabilities Section */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.4 }}
          className="mt-24 pt-16 border-t border-border/40"
        >
          <div className="text-center mb-12">
            <h3 className="font-serif text-3xl mb-4">We Orchestrate Your Business Logic</h3>
            <p className="text-muted-foreground max-w-2xl mx-auto">
              Need to capture deposits? Enforce strict cancellation policies? Verify insurance?
              We build custom logic adapters to handle your specific business complexity.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            {/* Card 1: Payments */}
            <div className="bg-muted/20 border border-border/50 p-8 rounded-2xl">
              <div className="w-12 h-12 bg-background rounded-xl flex items-center justify-center mb-6 border border-border shadow-sm">
                <CreditCard size={24} className="text-foreground" />
              </div>
              <h4 className="font-serif text-xl mb-3">Secure Payments</h4>
              <p className="text-sm text-muted-foreground leading-relaxed">
                Auto generation of payment links and pre-auth capture to secure every booking. We act as your financial safety net.
              </p>
            </div>

            {/* Card 2: Custom Workflows */}
            <div className="bg-muted/20 border border-border/50 p-8 rounded-2xl">
              <div className="w-12 h-12 bg-background rounded-xl flex items-center justify-center mb-6 border border-border shadow-sm">
                <Workflow size={24} className="text-foreground" />
              </div>
              <h4 className="font-serif text-xl mb-3">Custom Workflows</h4>
              <p className="text-sm text-muted-foreground leading-relaxed">
                Flexible logic that adapts to your unique operational rules by building custom workflows around your business.
              </p>
            </div>

            {/* Card 3: Revenue Protection */}
            <div className="bg-muted/20 border border-border/50 p-8 rounded-2xl">
              <div className="w-12 h-12 bg-background rounded-xl flex items-center justify-center mb-6 border border-border shadow-sm">
                <ShieldCheck size={24} className="text-foreground" />
              </div>
              <h4 className="font-serif text-xl mb-3">Revenue Protection</h4>
              <p className="text-sm text-muted-foreground leading-relaxed">
                Enforce deposits, manage strict cancellation policies, and gap fill efficiently. We protect your bottom line.
              </p>
            </div>
          </div>
        </motion.div>

      </div >
    </section >
  )
}
