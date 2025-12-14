"use client"

import React from "react"

import { motion, AnimatePresence, useScroll, useTransform, useMotionValueEvent } from "framer-motion"
import { useState, useEffect, useRef } from "react"
import { MessageCircleMore } from "@/components/animate-ui/icons/message-circle-more"
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


// Diagram nodes with Animate UI icons
const diagramNodes = [
  {
    id: "client",
    label: "Client Message",
    description: "Customer sends inquiry via WhatsApp asking about availability and pricing",
    x: 18,
    y: 18,
    icon: MessageCircleMore,
    animation: "default", // Typing/bouncing dots animation
    mockup: (
      <div className="space-y-2 w-full">
        <div className="flex items-start gap-2">
          <div className="w-6 h-6 rounded-full bg-white/10 flex items-center justify-center text-[10px]">C</div>
          <div className="flex-1 bg-white/5 rounded-lg p-2">
            <p className="text-[10px] text-white/80 leading-tight">Hi! Availability for gel nails tomorrow at 2pm?</p>
          </div>
        </div>
        <motion.div
          animate={{ opacity: [0.5, 1, 0.5] }}
          transition={{ duration: 1.5, repeat: Infinity }}
          className="flex items-center gap-1 text-[9px] text-white/40"
        >
          <div className="w-1.5 h-1.5 bg-green-400 rounded-full"></div>
          <span>Message received...</span>
        </motion.div>
      </div>
    )
  },
  {
    id: "Ovela",
    label: "Ovela AI",
    description: "AI analyzes intent, extracts service type, time preference, and urgency level",
    x: 72,
    y: 28,
    icon: Sparkles,
    animation: "path-loop", // Sparkle/twinkle animation
    mockup: (
      <motion.div
        animate={{ scale: [1, 1.02, 1] }}
        transition={{ duration: 2, repeat: Infinity }}
        className="bg-gradient-to-br from-blue-500/20 to-purple-500/20 rounded-lg p-2 border border-blue-500/30 w-full"
      >
        <div className="flex items-center gap-1 mb-1.5">
          <div className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-pulse"></div>
          <span className="text-[9px] text-white/60">Processing...</span>
        </div>
        <div className="space-y-0.5 text-[9px]">
          <div className="flex justify-between"><span className="text-white/40">Service:</span><span className="text-green-400">Gel Nails</span></div>
          <div className="flex justify-between"><span className="text-white/40">Time:</span><span className="text-green-400">Tomorrow 2pm</span></div>
          <div className="flex justify-between"><span className="text-white/40">Intent:</span><span className="text-green-400">Booking</span></div>
        </div>
      </motion.div>
    )
  },
  {
    id: "calendar",
    label: "Calendar & Availability",
    description: "System checks real-time calendar for available slots and finds matching times",
    x: 22,
    y: 68,
    icon: ClipboardList,
    animation: "path-loop", // List items appearing animation
    mockup: (
      <div className="grid grid-cols-3 gap-1.5 w-full">
        {["1:00pm", "2:00pm", "3:00pm"].map((time, i) => (
          <motion.div
            key={time}
            animate={{
              borderColor: i === 1 ? ["rgba(34,197,94,0.3)", "rgba(34,197,94,1)", "rgba(34,197,94,0.3)"] : "rgba(255,255,255,0.1)",
              backgroundColor: i === 1 ? ["rgba(34,197,94,0.1)", "rgba(34,197,94,0.2)", "rgba(34,197,94,0.1)"] : "transparent"
            }}
            transition={{ duration: 2, repeat: Infinity }}
            className="border rounded p-1 text-center"
          >
            <div className="text-white/60 text-[9px]">{time}</div>
            {i === 1 && <div className="text-green-400 text-[7px] mt-0.5">Available</div>}
          </motion.div>
        ))}
      </div>
    )
  },
  {
    id: "confirm",
    label: "Booking Confirmed",
    description: "Instant confirmation sent to client with booking details and calendar invite",
    x: 70,
    y: 82,
    icon: CircleCheckBig,
    animation: "path-loop", // Checkmark drawing animation
    mockup: (
      <motion.div
        animate={{ scale: [0.98, 1, 0.98] }}
        transition={{ duration: 2, repeat: Infinity }}
        className="bg-green-500/10 border border-green-500/30 rounded-lg p-2 w-full"
      >
        <div className="flex items-center gap-1.5 mb-1.5">
          <div className="w-4 h-4 rounded-full bg-green-500/20 flex items-center justify-center">
            <svg viewBox="0 0 16 16" fill="none" className="w-2.5 h-2.5" stroke="currentColor" strokeWidth="2">
              <path d="M3 8l3 3 7-7" />
            </svg>
          </div>
          <span className="text-[10px] font-medium text-green-400">Booking Confirmed!</span>
        </div>
        <div className="text-[9px] text-white/60 space-y-0.5">
          <div>📅 Tomorrow at 2:00 PM</div>
          <div>💅 Gel Nails - 60 min</div>
        </div>
      </motion.div>
    )
  }
]

const connections = [
  { from: "client", to: "Ovela" },
  { from: "Ovela", to: "calendar" },
  { from: "calendar", to: "confirm" },
]

export function ProblemSolution() {
  const [activePain, setActivePain] = useState(0)
  const containerRef = useRef<HTMLDivElement>(null)
  const [isAutopilot, setIsAutopilot] = useState(false)
  const [activeStep, setActiveStep] = useState(0)

  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ["start center", "end center"],
  })

  // Map scroll to step progression
  const scrollBasedStep = useTransform(scrollYProgress, [0, 0.9], [0, diagramNodes.length])

  useMotionValueEvent(scrollYProgress, "change", (latest: number) => {
    if (latest > 0.95 && !isAutopilot) {
      setIsAutopilot(true)
    }
  })

  // Autopilot loop
  useEffect(() => {
    if (!isAutopilot) return
    const interval = setInterval(() => {
      setActiveStep((prev) => (prev + 1) % diagramNodes.length)
    }, 2500)
    return () => clearInterval(interval)
  }, [isAutopilot])

  // Update active step from scroll
  useMotionValueEvent(scrollBasedStep, "change", (latest: number) => {
    if (!isAutopilot) {
      setActiveStep(Math.floor(latest))
    }
  })

  // Cycle pain points
  useEffect(() => {
    const interval = setInterval(() => {
      setActivePain((prev) => (prev + 1) % painPoints.length)
    }, 3000)
    return () => clearInterval(interval)
  }, [])

  // Pure curved wires (S-curve)
  const getPath = (fromId: string, toId: string) => {
    const from = diagramNodes.find(n => n.id === fromId)
    const to = diagramNodes.find(n => n.id === toId)
    if (!from || !to) return ""

    const x1 = from.x
    const y1 = from.y + 9
    const x2 = to.x
    const y2 = to.y - 9

    // Horizontal S-curve logic for zigzag flow
    // Control points pull horizontally from start and end
    const cp1x = (x1 + x2) / 2
    const cp1y = y1
    const cp2x = (x1 + x2) / 2
    const cp2y = y2

    // For a more "pure" curve that handles the vertical distance well:
    // We want to exit horizontally and enter horizontally if possible, 
    // but since they are stacked vertically, maybe a vertical exit/entry is better?
    // Actually, looking at the layout, nodes are at (18, 18) -> (72, 28).
    // This is a diagonal down-right.
    // Then (72, 28) -> (22, 68). Diagonal down-left.
    // A simple straight line with slight curve looks best.
    // Let's try a curve that emphasizes the flow.

    return `M ${x1} ${y1} C ${x1 + (x2 - x1) * 0.5} ${y1}, ${x2 - (x2 - x1) * 0.5} ${y2}, ${x2} ${y2}`
  }

  return (
    <section className="py-32 px-6 bg-card overflow-hidden">
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

        {/* Solution Diagram */}
        <motion.div
          ref={containerRef}
          initial={{ opacity: 0, y: 40 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.8 }}
          className="relative"
        >
          <p className="text-sm text-muted-foreground uppercase tracking-[0.2em] mb-4 text-center">The Solution</p>
          <h2 className="font-serif text-4xl md:text-5xl text-center mb-16 text-balance">
            AI That Talks. Sells. Books.
            <br />
            <span className="italic">Follows Up.</span>
          </h2>
          <p className="text-center text-muted-foreground max-w-2xl mx-auto mb-16 -mt-10">
            Don’t hope customers book. <strong className="text-foreground">Make sure they do.</strong>
          </p>

          {/* Diagram Container - Desktop (Hidden on Mobile) */}
          <div className="hidden md:block relative bg-black/40 rounded-3xl border border-white/10 p-8 min-h-[800px] overflow-hidden">
            {/* Grid background */}
            <div className="absolute inset-0 opacity-20">
              <svg width="100%" height="100%">
                <defs>
                  <pattern id="grid" width="30" height="30" patternUnits="userSpaceOnUse">
                    <path d="M 30 0 L 0 0 0 30" fill="none" stroke="currentColor" strokeWidth="0.5" className="text-white/20" />
                  </pattern>
                </defs>
                <rect width="100%" height="100%" fill="url(#grid)" />
              </svg>
            </div>

            {/* SVG Wires - Enhanced Curves */}
            <svg className="absolute inset-0 w-full h-full pointer-events-none" viewBox="0 0 100 100" preserveAspectRatio="none">
              <defs>
                <linearGradient id="wireGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="#C7B8A8" stopOpacity="0.2" />
                  <stop offset="50%" stopColor="#C7B8A8" stopOpacity="1" />
                  <stop offset="100%" stopColor="#C7B8A8" stopOpacity="0.2" />
                </linearGradient>
                <filter id="glow">
                  <feGaussianBlur stdDeviation="2" result="blur" />
                  <feMerge>
                    <feMergeNode in="blur" />
                    <feMergeNode in="SourceGraphic" />
                  </feMerge>
                </filter>
              </defs>

              {connections.map((conn, idx) => {
                const path = getPath(conn.from, conn.to)
                const isActive = activeStep > idx

                return (
                  <g key={`${conn.from}-${conn.to}`}>
                    {/* Base wire - dashed */}
                    <path
                      d={path}
                      fill="none"
                      stroke="rgba(199,184,168,0.2)"
                      strokeWidth="0.3"
                      strokeDasharray="2 2"
                    />

                    {/* Active wire - animated */}
                    <motion.path
                      d={path}
                      fill="none"
                      stroke="url(#wireGradient)"
                      strokeWidth="0.6"
                      initial={{ pathLength: 0, opacity: 0 }}
                      animate={{
                        pathLength: isActive ? 1 : 0,
                        opacity: isActive ? 1 : 0
                      }}
                      transition={{ duration: 1.2, ease: "easeInOut" }}
                    />

                    {/* Energy ball - flowing */}
                    {activeStep === idx + 1 && (
                      <circle r="0.7" fill="#C7B8A8" filter="url(#glow)">
                        <animateMotion
                          dur="2.5s"
                          repeatCount="indefinite"
                          path={path}
                        />
                      </circle>
                    )}
                  </g>
                )
              })}
            </svg>

            {/* Node Boxes */}
            {diagramNodes.map((node, index) => {
              const isActive = activeStep >= index
              const isCurrent = activeStep === index

              return (
                <div
                  key={node.id}
                  className="absolute"
                  style={{
                    left: `${node.x}%`,
                    top: `${node.y}%`,
                    transform: 'translate(-50%, -50%)'
                  }}
                >
                  <motion.div
                    animate={{
                      scale: isCurrent ? 1.05 : 1,
                      boxShadow: isCurrent
                        ? "0 0 50px rgba(199,184,168,0.5)"
                        : isActive
                          ? "0 0 25px rgba(199,184,168,0.25)"
                          : "none"
                    }}
                    transition={{ duration: 0.4 }}
                    className={`relative bg-black/90 backdrop-blur-sm rounded-2xl border-2 transition-colors duration-300 ${isActive ? "border-accent/60" : "border-white/10"
                      }`}
                    style={{ width: '230px', minHeight: '190px', padding: '22px' }}
                  >
                    {/* Pulse rings - Reduced Size */}
                    {isCurrent && (
                      <>
                        <motion.div
                          animate={{ scale: [1, 1.15], opacity: [0.5, 0] }}
                          transition={{ duration: 2, repeat: Infinity }}
                          className="absolute inset-0 rounded-2xl border-2 border-accent"
                        />
                        <motion.div
                          animate={{ scale: [1, 1.25], opacity: [0.3, 0] }}
                          transition={{ duration: 2, repeat: Infinity, delay: 0.5 }}
                          className="absolute inset-0 rounded-2xl border-2 border-accent"
                        />
                      </>
                    )}

                    {/* Animate UI Icon */}
                    <div className="flex items-center justify-center mb-4">
                      <node.icon
                        size={48}
                        animation={node.animation as any}
                        animate={isCurrent}
                        loop={isCurrent}
                        className={`transition-colors duration-500 ${isActive ? "text-accent" : "text-white/30"}`}
                      />
                    </div>

                    {/* Mockup */}
                    <div className="relative z-10">
                      {node.mockup}
                    </div>

                    {/* Step badge */}
                    <div className={`absolute -top-3 -right-3 w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold transition-all duration-300 ${isActive ? "bg-accent text-black scale-110" : "bg-white/10 text-white/40"
                      }`}>
                      {index + 1}
                    </div>
                  </motion.div>
                </div>
              )
            })}

            {/* Side Panel */}
            <AnimatePresence mode="wait">
              <motion.div
                key={activeStep}
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                transition={{ duration: 0.3 }}
                className="absolute right-8 top-1/2 -translate-y-1/2 max-w-[300px]"
              >
                <div className="space-y-3">
                  <div className="flex items-center gap-2 text-accent/60">
                    {diagramNodes[activeStep]?.icon && React.createElement(diagramNodes[activeStep].icon, { className: "w-4 h-4", strokeWidth: 2 })}
                    <span className="text-xs uppercase tracking-wider font-medium">STEP {activeStep + 1}</span>
                  </div>
                  <h3 className="font-serif text-2xl text-white">{diagramNodes[activeStep]?.label}</h3>
                  <p className="text-sm text-white/60 leading-relaxed">{diagramNodes[activeStep]?.description}</p>
                </div>
              </motion.div>
            </AnimatePresence>
          </div>

          {/* Mobile Cards - Sequential Process (Visible on Mobile) */}
          <div className="md:hidden space-y-6">
            {diagramNodes.map((node, index) => (
              <motion.div
                key={node.id}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-50px" }}
                transition={{ duration: 0.5, delay: index * 0.1 }}
                className="relative bg-zinc-950 rounded-2xl border border-white/10 overflow-hidden shadow-xl"
              >
                {/* Connecting Line (except for last item) */}
                {index < diagramNodes.length - 1 && (
                  <div className="absolute left-8 bottom-0 w-0.5 h-6 bg-gradient-to-b from-accent/50 to-transparent -mb-6 z-0" />
                )}

                <div className="p-6">
                  <div className="flex items-start gap-4">
                    {/* Icon Container */}
                    <div className="relative shrink-0">
                      <div className="w-16 h-16 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center">
                        <node.icon
                          size={32}
                          animation={node.animation as any}
                          animate={true}
                          loop={true}
                          className="text-accent"
                        />
                      </div>
                      {/* Step Badge */}
                      <div className="absolute -top-2 -right-2 w-6 h-6 rounded-full bg-accent text-black flex items-center justify-center text-xs font-bold shadow-lg shadow-accent/20">
                        {index + 1}
                      </div>
                    </div>

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <h3 className="font-serif text-xl text-zinc-100 mb-1">{node.label}</h3>
                      <p className="text-sm text-zinc-400 leading-relaxed mb-4">{node.description}</p>

                      {/* Mockup Container */}
                      <div className="bg-white/5 rounded-xl p-3 border border-white/5">
                        {node.mockup}
                      </div>
                    </div>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        </motion.div>
      </div>
    </section>
  )
}
