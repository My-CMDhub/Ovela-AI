"use client"

import React from "react"
import { motion, AnimatePresence } from "framer-motion"
import { useState, useEffect } from "react"
import { PhoneCall } from "@/components/animate-ui/icons/phone-call"
import { Sparkles } from "@/components/animate-ui/icons/sparkles"
import { ClipboardList } from "@/components/animate-ui/icons/clipboard-list"
import { CircleCheckBig } from "@/components/animate-ui/icons/circle-check-big"

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
      <div className="space-y-2" key={isActive ? "active" : "inactive"}>
        <div className="flex items-center gap-2">
          <motion.div
            animate={isActive ? { scale: [1, 1.2, 1] } : { scale: 1 }}
            transition={{ duration: 1.5, repeat: isActive ? Infinity : 0 }}
            className="w-3 h-3 rounded-full bg-accent"
          />
          <span className="text-xs text-muted-foreground">Incoming call...</span>
        </div>
        {isActive && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.3, delay: 0.5 }}
            className="text-xs font-medium"
          >
            {/* Typewriter effect */}
            <motion.span
              initial={{ width: 0 }}
              animate={{ width: "100%" }}
              transition={{ duration: 1.5, delay: 0.8, ease: "linear" }}
              className="inline-block overflow-hidden whitespace-nowrap"
            >
              "Hi, do you have availability?"
            </motion.span>
          </motion.div>
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
      <div className="space-y-1.5" key={isActive ? "active" : "inactive"}>
        {/* Processing indicator - only shows when active */}
        {isActive && (
          <motion.div
            initial={{ opacity: 1 }}
            animate={{ opacity: 0 }}
            transition={{ duration: 0.3, delay: 1.5 }}
            className="flex items-center gap-1 text-xs text-muted-foreground"
          >
            <motion.div
              animate={{ opacity: [0.3, 1, 0.3] }}
              transition={{ duration: 1, repeat: Infinity }}
              className="w-1 h-1 rounded-full bg-accent"
            />
            <motion.div
              animate={{ opacity: [0.3, 1, 0.3] }}
              transition={{ duration: 1, repeat: Infinity, delay: 0.2 }}
              className="w-1 h-1 rounded-full bg-accent"
            />
            <motion.div
              animate={{ opacity: [0.3, 1, 0.3] }}
              transition={{ duration: 1, repeat: Infinity, delay: 0.4 }}
              className="w-1 h-1 rounded-full bg-accent"
            />
            <span className="ml-1">Processing...</span>
          </motion.div>
        )}

        {/* Data extraction - sequential reveal */}
        {["Service: Hair Cut", "Time: Tomorrow 2pm", "Intent: Booking"].map((item, i) => (
          <motion.div
            key={item}
            initial={{ opacity: 0, x: -10 }}
            animate={isActive ? { opacity: 1, x: 0 } : { opacity: 0, x: -10 }}
            transition={{ delay: isActive ? 0.5 + i * 0.4 : 0, duration: 0.4 }}
            className="flex items-center gap-2 text-xs"
          >
            <motion.div
              initial={{ scale: 0 }}
              animate={isActive ? { scale: 1 } : { scale: 0 }}
              transition={{ delay: isActive ? 0.5 + i * 0.4 : 0, type: "spring", stiffness: 300 }}
              className="w-1 h-1 rounded-full bg-accent"
            />
            <span className="text-muted-foreground">{item}</span>
          </motion.div>
        ))}
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
      <div className="relative" key={isActive ? "active" : "inactive"}>
        <div className="grid grid-cols-3 gap-1.5">
          {["1pm", "2pm", "3pm"].map((time, i) => (
            <motion.div
              key={time}
              animate={
                isActive
                  ? {
                    // Hover effect: border changes when cursor is over
                    borderColor:
                      i === 0
                        ? ["hsl(var(--border))", "hsl(var(--accent))", "hsl(var(--border))", "hsl(var(--border))"]
                        : i === 1
                          ? ["hsl(var(--border))", "hsl(var(--border))", "hsl(var(--accent))", "hsl(var(--accent))"]
                          : "hsl(var(--border))",
                    backgroundColor:
                      i === 1
                        ? ["transparent", "transparent", "hsl(var(--accent) / 0.1)", "hsl(var(--accent) / 0.1)"]
                        : "transparent",
                    // Click effect on 2pm
                    scale: i === 1 ? [1, 1, 1, 0.95, 1] : 1,
                  }
                  : {
                    borderColor: "hsl(var(--border))",
                    backgroundColor: "transparent",
                    scale: 1,
                  }
              }
              transition={{
                duration: 3,
                times: i === 0 ? [0, 0.3, 0.5, 1] : i === 1 ? [0, 0.3, 0.6, 0.7, 0.75] : [0, 1],
                ease: "easeInOut",
              }}
              className="border rounded p-1.5 text-center relative"
            >
              <div className="text-[10px] font-medium">{time}</div>
              {i === 1 && isActive && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: 2.3, duration: 0.2, type: "spring" }}
                  className="text-[8px] text-accent mt-0.5 font-medium"
                >
                  Open
                </motion.div>
              )}
            </motion.div>
          ))}
        </div>

        {/* Animated cursor pointer - hovers through each slot realistically */}
        {isActive && (
          <motion.div
            initial={{ opacity: 0, x: -20, y: 5 }}
            animate={{
              opacity: [0, 1, 1, 1, 1, 1, 0],
              x: [-20, 8, 8, 43, 43, 43, 43],
              y: [5, 5, 5, 5, 5, 5, 5],
            }}
            transition={{
              duration: 3,
              times: [0, 0.15, 0.45, 0.55, 0.85, 0.95, 1],
              ease: "easeInOut",
            }}
            className="absolute pointer-events-none z-10"
            style={{ left: "0", top: "50%", transform: "translateY(-50%)" }}
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" className="text-foreground drop-shadow-lg">
              <path d="M2 2L10 7L6 10L2 2Z" fill="currentColor" stroke="white" strokeWidth="0.5" />
            </svg>
          </motion.div>
        )}
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
      <div className="space-y-2" key={isActive ? "active" : "inactive"}>
        {isActive && (
          <>
            <motion.div
              initial={{ scale: 0, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ type: "spring", stiffness: 200, delay: 0.2 }}
              className="flex items-center gap-2"
            >
              <motion.div
                initial={{ rotate: -90 }}
                animate={{ rotate: 0 }}
                transition={{ type: "spring", stiffness: 200, delay: 0.4 }}
                className="w-4 h-4 rounded-full bg-accent/20 flex items-center justify-center"
              >
                <motion.svg
                  viewBox="0 0 16 16"
                  className="w-2.5 h-2.5 text-accent"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.5"
                  initial={{ pathLength: 0 }}
                  animate={{ pathLength: 1 }}
                  transition={{ duration: 0.4, delay: 0.6 }}
                >
                  <motion.path d="M3 8l3 3 7-7" />
                </motion.svg>
              </motion.div>
              <motion.span
                initial={{ opacity: 0, x: -5 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.7, duration: 0.3 }}
                className="text-xs font-medium text-accent"
              >
                Confirmed!
              </motion.span>
            </motion.div>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 1, duration: 0.3 }}
              className="text-[10px] text-muted-foreground"
            >
              Tomorrow at 2:00 PM
            </motion.div>
          </>
        )}
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

          {/* Desktop: Horizontal Flow */}
          <div className="hidden md:grid md:grid-cols-4 gap-6">
            {solutionSteps.map((item, index) => (
              <motion.div
                key={item.step}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: index * 0.1 }}
                onMouseEnter={() => setActiveStep(index)}
                className="relative group"
              >
                {/* Connecting line */}
                {index < solutionSteps.length - 1 && (
                  <div className="absolute top-12 left-[calc(50%+32px)] w-[calc(100%-32px)] h-[2px] bg-border/50 z-0">
                    <motion.div
                      className="h-full bg-accent origin-left"
                      initial={{ scaleX: 0 }}
                      animate={{ scaleX: activeStep > index ? 1 : 0 }}
                      transition={{ duration: 0.5, delay: 0.2 }}
                    />
                  </div>
                )}

                <div
                  className={`relative bg-background border rounded-2xl p-6 transition-all duration-500 ${activeStep === index ? "border-accent shadow-lg shadow-accent/10" : "border-border/50"
                    }`}
                >
                  {/* Step number badge */}
                  <div
                    className={`absolute -top-3 -right-3 w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-all duration-300 ${activeStep >= index ? "bg-accent text-accent-foreground" : "bg-muted text-muted-foreground"
                      }`}
                  >
                    {item.step}
                  </div>

                  {/* Icon */}
                  <motion.div
                    animate={{ scale: activeStep === index ? 1.1 : 1 }}
                    transition={{ duration: 0.3 }}
                    className={`w-14 h-14 rounded-2xl flex items-center justify-center mb-5 transition-all duration-300 ${activeStep === index ? "bg-accent/20" : "bg-muted"
                      }`}
                  >
                    <item.Icon
                      size={28}
                      className={`transition-colors duration-300 ${activeStep === index ? "text-accent" : "text-muted-foreground"
                        }`}
                      animate={activeStep === index}
                      animation="default"
                      loop={true}
                    />
                  </motion.div>

                  <h3 className="font-serif text-xl mb-2">{item.title}</h3>
                  <p className="text-sm text-muted-foreground mb-5">{item.description}</p>

                  {/* Visual Mockup */}
                  <div className="mb-5 p-3 rounded-lg bg-muted/30 border border-border/50 min-h-[120px] flex items-center">
                    {item.mockup(activeStep === index)}
                  </div>

                  {/* Stats - matching Problem section style */}
                  <div className="pt-5 border-t border-border/30">
                    <div className="flex items-end gap-2">
                      <motion.span
                        animate={{ opacity: activeStep === index ? 1 : 0.5 }}
                        className="font-serif text-3xl text-accent"
                      >
                        {item.detail}
                      </motion.span>
                      <span className="text-xs text-muted-foreground mb-1">{item.detailLabel}</span>
                    </div>
                  </div>

                  {/* Progress bar - matching Problem section */}
                  <AnimatePresence>
                    {activeStep === index && (
                      <motion.div
                        initial={{ scaleX: 0 }}
                        animate={{ scaleX: 1 }}
                        exit={{ scaleX: 0 }}
                        transition={{ duration: 3.5, ease: "linear" }}
                        className="absolute bottom-0 left-0 right-0 h-[2px] bg-accent origin-left"
                        style={{ borderBottomLeftRadius: "1rem", borderBottomRightRadius: "1rem" }}
                      />
                    )}
                  </AnimatePresence>
                </div>
              </motion.div>
            ))}
          </div>

          {/* Mobile: Vertical Stack */}
          <div className="md:hidden space-y-4">
            {solutionSteps.map((item, index) => (
              <motion.div
                key={item.step}
                initial={{ opacity: 0, x: -20 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true, margin: "-50px" }}
                transition={{ duration: 0.4, delay: index * 0.1 }}
                className="relative"
              >
                {/* Vertical connecting line */}
                {index < solutionSteps.length - 1 && (
                  <div className="absolute left-7 top-[72px] w-[2px] h-4 bg-accent/30" />
                )}

                <div className="bg-background border border-border/50 rounded-2xl p-5 space-y-4">
                  <div className="flex items-start gap-4">
                    {/* Icon */}
                    <div className="shrink-0 w-14 h-14 rounded-2xl bg-accent/10 flex items-center justify-center">
                      <item.Icon size={26} className="text-accent" animation="default" loop />
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-xs font-bold text-accent">Step {item.step}</span>
                      </div>
                      <h3 className="font-serif text-lg mb-1">{item.title}</h3>
                      <p className="text-sm text-muted-foreground">{item.description}</p>
                    </div>
                  </div>

                  {/* Visual Mockup */}
                  <div className="p-3 rounded-lg bg-muted/30 border border-border/50 min-h-[70px] flex items-center">
                    {item.mockup(true)}
                  </div>

                  {/* Stats */}
                  <div className="pt-4 border-t border-border/30">
                    <div className="flex items-end gap-2">
                      <span className="font-serif text-3xl text-accent">{item.detail}</span>
                      <span className="text-xs text-muted-foreground mb-1">{item.detailLabel}</span>
                    </div>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        </motion.div>
      </div >
    </section >
  )
}
