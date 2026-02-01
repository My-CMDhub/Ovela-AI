"use client"

import type React from "react"
import { motion, useMotionValue, useSpring, AnimatePresence } from "framer-motion"
import { useState, useEffect } from "react"
import { EcosystemLoop } from "@/components/ecosystem-loop"
import { TextRotator } from "@/components/text-rotator"
import { VoiceDemoForm } from "@/components/VoiceDemoForm"
import { ArrowRight, X, Check, ShieldCheck } from "lucide-react"
import Link from "next/link"
import Image from "next/image"

// Recent calls handled by AI (industry-agnostic)
const recentCalls = [
  { id: 1, caller: "David M.", type: "Booking Request", time: "10:02 AM", status: "synced", avatar: "D" },
  { id: 2, caller: "Sarah K.", type: "Availability Check", time: "10:15 AM", status: "responded", avatar: "S" },
  { id: 3, caller: "James L.", type: "Quote Request", time: "10:28 AM", status: "forwarded", avatar: "J" },
  { id: 4, caller: "Emma R.", type: "Appointment", time: "10:45 AM", status: "synced", avatar: "E" },
  { id: 5, caller: "Michael T.", type: "Callback Request", time: "11:02 AM", status: "pending", avatar: "M" },
]

const stats = [
  { label: "Calls Handled", value: "47", change: "+12" },
  { label: "Bookings Made", value: "23", change: "+8" },
  { label: "Hours Saved", value: "6.5h", change: "+2h" },
]

function FloatingParticles() {
  // Use motion values for zero re-renders
  const mouseX = useMotionValue(0)
  const mouseY = useMotionValue(0)

  // Ultra-smooth spring physics - Olivier Larose technique
  const smoothOptions = { damping: 20, stiffness: 300, mass: 0.5 }
  const smoothX = useSpring(mouseX, smoothOptions)
  const smoothY = useSpring(mouseY, smoothOptions)

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      const section = document.querySelector('section')
      if (section) {
        const rect = section.getBoundingClientRect()
        // Set motion values directly - no re-renders!
        mouseX.set(e.clientX - rect.left - 300)
        mouseY.set(e.clientY - rect.top - 300)
      }
    }

    window.addEventListener('mousemove', handleMouseMove, { passive: true })
    return () => window.removeEventListener('mousemove', handleMouseMove)
  }, [mouseX, mouseY])

  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      {/* Cursor-following gradient orb with ultra-smooth spring animation */}
      <motion.div
        style={{
          x: smoothX,
          y: smoothY,
        }}
        className="absolute w-[500px] h-[500px] rounded-full"
        initial={{ opacity: 0 }}
        animate={{
          opacity: 0.5,
          scale: [1, 1.05, 1]
        }}
        transition={{
          opacity: { duration: 0.5 },
          scale: { duration: 8, repeat: Infinity, ease: "easeInOut" }
        }}
      >
        <div
          className="w-full h-full rounded-full"
          style={{
            background: "var(--orb-gradient)",
            filter: "blur(40px)",
            willChange: "transform"
          }}
        />
      </motion.div>


      {/* Grid/Panel pattern revealed by orb light */}
      <motion.div
        style={
          {
            x: smoothX,
            y: smoothY,
          }
        }
        className="absolute w-[800px] h-[800px] pointer-events-none"
      >
        {/* Radial gradient mask that reveals the grid */}
        <div
          className="relative w-full h-full"
          style={{
            maskImage: "radial-gradient(circle 400px at center, black 0%, transparent 70%)",
            WebkitMaskImage: "radial-gradient(circle 400px at center, black 0%, transparent 70%)",
          }}
        >
          {/* Dot grid pattern */}
          <svg className="absolute inset-0 w-full h-full" xmlns="http://www.w3.org/2000/svg">
            <defs>
              <pattern id="grid-dots" width="40" height="40" patternUnits="userSpaceOnUse">
                <circle cx="20" cy="20" r="1.5" fill="rgba(200,180,168,0.4)" />
              </pattern>
            </defs>
            <rect width="100%" height="100%" fill="url(#grid-dots)" />
          </svg>

          {/* Line grid pattern */}
          <svg className="absolute inset-0 w-full h-full opacity-30" xmlns="http://www.w3.org/2000/svg">
            <defs>
              <pattern id="grid-lines" width="40" height="40" patternUnits="userSpaceOnUse">
                <path d="M 40 0 L 0 0 0 40" fill="none" stroke="rgba(200,180,168,0.3)" strokeWidth="0.5" />
              </pattern>
            </defs>
            <rect width="100%" height="100%" fill="url(#grid-lines)" />
          </svg>
        </div>
      </motion.div>
    </div>
  )
}

function MacBookMockup({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative">
      {/* Glow/reflection underneath */}
      <div className="absolute -inset-8 bg-gradient-to-b from-accent/10 via-accent/5 to-transparent rounded-[60px] blur-3xl -z-10" />
      <div className="absolute -bottom-10 left-1/2 -translate-x-1/2 w-3/4 h-10 bg-black/10 rounded-full blur-3xl -z-10" />

      {/* Main MacBook Frame */}
      <div className="relative">
        {/* Screen Assembly */}
        <div
          className="relative bg-[#1d1d1f] rounded-t-[16px] p-[8px]"
          style={{
            boxShadow: `
              0 0 0 1px rgba(255,255,255,0.05),
              inset 0 0 0 1px rgba(0,0,0,0.3),
              0 25px 50px -12px rgba(0,0,0,0.4),
              0 12px 24px -8px rgba(0,0,0,0.3)
            `,
          }}
        >
          {/* Webcam */}
          <div className="absolute top-[3px] left-1/2 -translate-x-1/2 z-20">
            <div className="w-[6px] h-[6px] rounded-full bg-[#3a3a3c] flex items-center justify-center">
              <div className="w-[3px] h-[3px] rounded-full bg-[#0a0a0a] ring-[0.5px] ring-[#2a2a2c]" />
            </div>
          </div>

          {/* Screen bezel */}
          <div className="bg-black rounded-[10px] p-[2px]">
            {/* Actual screen */}
            <div className="bg-card rounded-[8px] overflow-hidden" style={{ aspectRatio: "16/10" }}>
              {children}
            </div>
          </div>
        </div>

        {/* Bottom chin / hinge cover */}
        <div
          className="relative h-[14px] bg-gradient-to-b from-[#3a3a3c] via-[#2d2d2f] to-[#1d1d1f] rounded-b-[16px] mx-[1px]"
          style={{
            boxShadow: `
              0 1px 0 rgba(255,255,255,0.05),
              inset 0 1px 2px rgba(0,0,0,0.3)
            `,
          }}
        >
          {/* Notch / Hinge detail */}
          <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[80px] h-[3px] bg-gradient-to-b from-[#2a2a2c] to-[#1d1d1f] rounded-b-full" />
        </div>

        {/* Base / Body */}
        <div className="relative mx-auto" style={{ width: "calc(100% + 8px)", marginLeft: "-4px" }}>
          {/* Base top surface */}
          <div
            className="h-[8px] bg-gradient-to-b from-[#4a4a4c] via-[#3a3a3c] to-[#2d2d2f] rounded-b-[12px]"
            style={{
              boxShadow: `
                0 4px 12px rgba(0,0,0,0.3),
                inset 0 1px 0 rgba(255,255,255,0.1)
              `,
            }}
          />
          {/* Bottom lip */}
          <div className="h-[3px] bg-gradient-to-b from-[#2d2d2f] to-[#1d1d1f] mx-2 rounded-b-lg" />
        </div>

        {/* Subtle reflection overlay on screen */}
        <div className="absolute top-0 left-0 right-0 h-1/3 bg-gradient-to-b from-white/[0.03] to-transparent rounded-t-[16px] pointer-events-none" />
      </div>
    </div>
  )
}

function IPhoneMockup() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 30 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.8, delay: 0.6 }}
      className="relative"
    >
      {/* Glow effect */}
      <div className="absolute -inset-4 bg-gradient-to-b from-blue-500/20 via-purple-500/10 to-transparent rounded-[50px] blur-2xl -z-10" />

      {/* iPhone Frame */}
      <div
        className="relative rounded-[44px] p-[3px] bg-gradient-to-b from-[#3a3a3c] to-[#1d1d1f]"
        style={{
          boxShadow: `
            0 0 0 1px rgba(255,255,255,0.1),
            0 25px 50px -12px rgba(0,0,0,0.5),
            inset 0 1px 0 rgba(255,255,255,0.1)
          `,
        }}
      >
        <div className="rounded-[42px] overflow-hidden bg-gradient-to-br from-blue-500 via-blue-400 to-blue-600" style={{ width: "200px", height: "400px" }}>
          {/* Status Bar */}
          <div className="flex items-center justify-between px-6 pt-3">
            <span className="text-white/90 text-[10px] font-medium">9:41</span>
            <div className="flex items-center gap-1">
              <svg className="w-3 h-3 text-white/90" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 18c3.31 0 6-2.69 6-6s-2.69-6-6-6-6 2.69-6 6 2.69 6 6 6z" />
              </svg>
              <svg className="w-4 h-3 text-white/90" fill="currentColor" viewBox="0 0 24 24">
                <rect x="2" y="7" width="18" height="10" rx="2" />
                <rect x="20" y="10" width="2" height="4" />
              </svg>
            </div>
          </div>

          {/* Incoming Call Content */}
          <div className="flex flex-col items-center pt-8 px-4">
            <p className="text-white/70 text-xs mb-1">incoming call</p>
            <h2 className="text-white text-2xl font-light mb-1">Ovela</h2>
            <h3 className="text-white text-3xl font-semibold tracking-tight">AI</h3>

            {/* Avatar - Stylized O logo */}
            <motion.div
              className="mt-6 w-24 h-24 rounded-full bg-gradient-to-br from-purple-400 via-pink-400 to-purple-500 flex items-center justify-center shadow-lg"
              animate={{ scale: [1, 1.02, 1] }}
              transition={{ duration: 2, repeat: Infinity }}
            >
              <div className="w-20 h-20 rounded-full bg-gradient-to-br from-purple-300 via-pink-300 to-purple-400 flex items-center justify-center">
                <span className="text-4xl font-serif font-bold text-white drop-shadow-sm">O</span>
              </div>
            </motion.div>
          </div>

          {/* Bottom Actions */}
          <div className="absolute bottom-8 left-0 right-0 flex flex-col items-center gap-4">
            {/* Remind Me / Message */}
            <div className="flex gap-8 mb-2">
              <div className="flex flex-col items-center gap-1">
                <div className="w-12 h-12 rounded-full bg-white/20 backdrop-blur flex items-center justify-center">
                  <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6l4 2m6-2a10 10 0 11-20 0 10 10 0 0120 0z" />
                  </svg>
                </div>
                <span className="text-white/70 text-[10px]">Remind Me</span>
              </div>
              <div className="flex flex-col items-center gap-1">
                <div className="w-12 h-12 rounded-full bg-white/20 backdrop-blur flex items-center justify-center">
                  <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                  </svg>
                </div>
                <span className="text-white/70 text-[10px]">Message</span>
              </div>
            </div>

            {/* Decline / Accept */}
            <div className="flex gap-12">
              {/* Decline */}
              <div className="flex flex-col items-center gap-1">
                <div className="w-14 h-14 rounded-full bg-red-500 flex items-center justify-center shadow-lg">
                  <svg className="w-7 h-7 text-white rotate-[135deg]" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M6.62 10.79c1.44 2.83 3.76 5.15 6.59 6.59l2.2-2.2c.27-.27.67-.36 1.02-.24 1.12.37 2.33.57 3.57.57.55 0 1 .45 1 1V20c0 .55-.45 1-1 1-9.39 0-17-7.61-17-17 0-.55.45-1 1-1h3.5c.55 0 1 .45 1 1 0 1.25.2 2.45.57 3.57.11.35.03.74-.25 1.02l-2.2 2.2z" />
                  </svg>
                </div>
                <span className="text-white/70 text-[10px]">Decline</span>
              </div>

              {/* Accept - with pulse animation */}
              <div className="flex flex-col items-center gap-1 relative">
                <motion.div
                  className="absolute inset-0 w-14 h-14 rounded-full bg-green-400"
                  animate={{ scale: [1, 1.3, 1], opacity: [0.5, 0, 0.5] }}
                  transition={{ duration: 1.5, repeat: Infinity }}
                />
                <div className="w-14 h-14 rounded-full bg-green-500 flex items-center justify-center shadow-lg relative">
                  <svg className="w-7 h-7 text-white" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M6.62 10.79c1.44 2.83 3.76 5.15 6.59 6.59l2.2-2.2c.27-.27.67-.36 1.02-.24 1.12.37 2.33.57 3.57.57.55 0 1 .45 1 1V20c0 .55-.45 1-1 1-9.39 0-17-7.61-17-17 0-.55.45-1 1-1h3.5c.55 0 1 .45 1 1 0 1.25.2 2.45.57 3.57.11.35.03.74-.25 1.02l-2.2 2.2z" />
                  </svg>
                </div>
                <span className="text-white/70 text-[10px]">Accept</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  )
}

export function Hero() {
  const [currentTime, setCurrentTime] = useState(new Date())
  const [activeBooking, setActiveBooking] = useState(0)
  const [isDemoOpen, setIsDemoOpen] = useState(false) // State for modal

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000)
    return () => clearInterval(timer)
  }, [])

  useEffect(() => {
    const callTimer = setInterval(() => {
      setActiveBooking((prev) => (prev + 1) % recentCalls.length)
    }, 2500)
    return () => clearInterval(callTimer)
  }, [])

  // Close modal on escape
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape") setIsDemoOpen(false)
    }
    window.addEventListener("keydown", handleEscape)
    return () => window.removeEventListener("keydown", handleEscape)
  }, [])

  // Open modal when navigating to #demo (from pricing "Try AI Demo" button)
  useEffect(() => {
    const handleOpenDemo = () => {
      setIsDemoOpen(true)
    }

    // Listen for custom event from other components
    window.addEventListener("openDemoModal", handleOpenDemo)

    // Also check for hash on mount (fallback)
    if (window.location.hash === "#demo") {
      setIsDemoOpen(true)
      window.history.replaceState(null, "", window.location.pathname)
    }

    return () => window.removeEventListener("openDemoModal", handleOpenDemo)
  }, [])


  return (
    <section className="relative min-h-screen flex flex-col pt-20 overflow-hidden">
      <FloatingParticles />

      <div className="relative z-10 max-w-6xl mx-auto px-6">
        <motion.div
          initial="hidden"
          animate="visible"
          variants={{
            hidden: { opacity: 0 },
            visible: {
              opacity: 1,
              transition: {
                staggerChildren: 0.15,
                delayChildren: 0.1
              }
            }
          }}
          className="text-center mb-16"
        >
          {/* Pill Badge */}
          <motion.div
            initial={{ opacity: 0, scale: 0.9, filter: "blur(4px)" }}
            animate={{ opacity: 1, scale: 1, filter: "blur(0px)" }}
            transition={{ duration: 0.5, ease: "easeOut" }}
            className="mb-6 inline-flex items-center rounded-full border border-primary/20 bg-primary/5 px-3 py-1 text-sm text-primary backdrop-blur-sm"
          >
            <span className="flex h-2 w-2 rounded-full bg-primary mr-2 animate-pulse"> </span>
            Native Integrations • ServiceM8 • RMS Cloud • Vagaro
          </motion.div>

          {/* Main Heading */}
          <motion.h1
            variants={
              {
                hidden: { opacity: 0, y: 20, filter: "blur(10px)" },
                visible: { opacity: 1, y: 0, filter: "blur(0px)", transition: { duration: 0.8, ease: "easeOut" } }
              }
            }
            initial="hidden"
            animate="visible"
            className="mx-auto max-w-4xl font-serif text-5xl font-medium tracking-tight text-foreground sm:text-7xl"
          >
            The AI Front Desk for <br />
            <span className="text-muted-foreground">
              <TextRotator
                texts={["ServiceM8", "RMS Cloud", "Tradify", "Cliniko", "Fergus", "Xero", "Halaxy", "Apaleo", "Zoho CRM", "Vagaro"]}
                className="font-serif italic"
              />
            </span>
          </motion.h1>

          {/* Subtitle */}
          <motion.p
            variants={
              {
                hidden: { opacity: 0, y: 20, filter: "blur(8px)" },
                visible: { opacity: 1, y: 0, filter: "blur(0px)", transition: { duration: 0.8, delay: 0.2, ease: "easeOut" } }
              }
            }
            initial="hidden"
            animate="visible"
            className="mx-auto mt-6 max-w-2xl text-lg text-muted-foreground sm:text-xl"
          >
            Answering calls, qualifying leads, and <strong className="text-foreground font-medium">injecting bookings directly</strong> into your schedule. No double-entry.
          </motion.p>

          {/* CTA Buttons */}
          <motion.div
            variants={
              {
                hidden: { opacity: 0, y: 20, filter: "blur(6px)" },
                visible: { opacity: 1, y: 0, filter: "blur(0px)", transition: { duration: 0.8, delay: 0.4, ease: "easeOut" } }
              }
            }
            initial="hidden"
            animate="visible"
            className="mt-8 flex flex-col items-center justify-center gap-4 sm:flex-row relative"
          >
            <Link
              href="#live-preview"
              className="inline-flex h-12 items-center justify-center rounded-full bg-primary px-8 text-base font-medium text-primary-foreground shadow transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50"
            >
              Hear It In Action
              <ArrowRight className="ml-2 h-4 w-4" />
            </Link>


            {/* Premium 'View Demo' Button with High-Class Motion Border */}
            <motion.button
              onClick={() => setIsDemoOpen(true)}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              className="relative inline-flex h-12 overflow-hidden rounded-full p-[1px] focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-background"
            >
              {/* Spinning Gradient Border - Brighter and smoother */}
              <span className="absolute inset-[-1000%] animate-[spin_3s_linear_infinite] bg-[conic-gradient(from_90deg_at_50%_50%,#0000_0%,#7c3aed_50%,#0000_100%)] opacity-100 transition-opacity duration-500 group-hover:opacity-100" />

              {/* Inner Background */}
              <span className="inline-flex h-full w-full items-center justify-center rounded-full bg-background/95 px-8 backdrop-blur-3xl transition-colors hover:bg-background/90">
                <span className="relative flex items-center gap-2 text-foreground font-medium">
                  {/* Text Reveal Animation */}
                  <span className="relative z-10 inline-flex overflow-hidden">
                    {"View Demo".split("").map((char, index) => (
                      <motion.span
                        key={index}
                        initial={{ y: 20, opacity: 0 }}
                        animate={{ y: 0, opacity: 1 }}
                        transition={{
                          duration: 0.5,
                          delay: 0.6 + index * 0.05,
                          ease: "easeOut",
                          repeat: Infinity,
                          repeatDelay: 3,
                        }}
                        className="inline-block"
                      >
                        {char === " " ? "\u00A0" : char}
                      </motion.span>
                    ))}
                  </span>
                </span>
              </span>
            </motion.button>

          </motion.div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 80, rotateX: 8 }}
          animate={{ opacity: 1, y: 0, rotateX: 0 }}
          transition={{ duration: 1.2, ease: "easeOut", delay: 0.5 }}
          className="relative mx-auto max-w-4xl"
          style={{ perspective: "1500px" }}
        >
          <MacBookMockup>
            {/* Browser chrome */}
            <div className="bg-muted/50 px-4 py-2 flex items-center gap-3 border-b border-border/30">
              <div className="flex items-center gap-1.5">
                <div className="w-3 h-3 rounded-full bg-[#ff5f57] hover:bg-[#ff5f57]/80 transition-colors" />
                <div className="w-3 h-3 rounded-full bg-[#ffbd2e] hover:bg-[#ffbd2e]/80 transition-colors" />
                <div className="w-3 h-3 rounded-full bg-[#28ca41] hover:bg-[#28ca41]/80 transition-colors" />
              </div>
              <div className="flex-1 max-w-md mx-auto">
                <div className="bg-background/80 backdrop-blur rounded-md px-4 py-1.5 text-xs text-muted-foreground flex items-center gap-2 border border-border/30">
                  <svg
                    className="w-3 h-3 text-green-600"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth="2"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
                    />
                  </svg>
                  ovela.dev/dashboard
                </div>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-6 h-6 rounded bg-muted/50 flex items-center justify-center">
                  <svg
                    className="w-3 h-3 text-muted-foreground"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                  >
                    <path d="M15 18l-6-6 6-6" />
                  </svg>
                </div>
                <div className="w-6 h-6 rounded bg-muted/50 flex items-center justify-center">
                  <svg
                    className="w-3 h-3 text-muted-foreground"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                  >
                    <path d="M9 18l6-6-6-6" />
                  </svg>
                </div>
              </div>
            </div>

            {/* Dashboard Content */}
            <div className="flex min-h-[380px]">
              {/* Sidebar */}
              <div className="w-52 bg-muted/30 border-r border-border/30 p-4 hidden md:block">
                <div className="flex items-center gap-3 mb-8">
                  <div className="w-9 h-9 rounded-xl bg-accent/20 flex items-center justify-center shadow-sm">
                    <span className="font-serif text-lg font-semibold">O</span>
                  </div>
                  <div>
                    <p className="font-semibold text-sm">Your Business</p>
                    <p className="text-xs text-muted-foreground">Connected to Ovela</p>
                  </div>
                </div>

                <nav className="space-y-1">
                  {
                    [
                      {
                        icon: "M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6",
                        label: "Dashboard",
                        active: true,
                      },
                      {
                        icon: "M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z",
                        label: "Bookings",
                        active: false,
                      },
                      {
                        icon: "M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z",
                        label: "Clients",
                        active: false,
                      },
                      {
                        icon: "M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z",
                        label: "Messages",
                        active: false,
                      },
                      {
                        icon: "M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37.996.608 2.296.07 2.572-1.065z",
                        label: "Settings",
                        active: false,
                      },
                    ].map((item, i) => (
                      <div
                        key={i}
                        className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${item.active
                          ? "bg-accent/20 text-foreground font-medium"
                          : "text-muted-foreground hover:bg-muted/50"
                          }`}
                      >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
                          <path strokeLinecap="round" strokeLinejoin="round" d={item.icon} />
                        </svg>
                        {item.label}
                      </div>
                    ))}
                </nav>
              </div>

              {/* Main Content */}
              <div className="flex-1 p-5 bg-background/50">
                {/* Header */}
                <div className="flex items-center justify-between mb-5">
                  <div>
                    <h2 className="text-base font-semibold"> Good morning, Lisa </h2>
                    <p className="text-xs text-muted-foreground">
                      {currentTime.toLocaleDateString("en-US", { weekday: "long", month: "short", day: "numeric" })}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="relative">
                      <div className="w-8 h-8 rounded-full bg-muted flex items-center justify-center">
                        <svg
                          className="w-4 h-4 text-muted-foreground"
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                          strokeWidth="1.5"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
                          />
                        </svg>
                      </div>
                      <div className="absolute -top-0.5 -right-0.5 w-2.5 h-2.5 bg-accent rounded-full border-2 border-card" />
                    </div>
                  </div>
                </div>

                {/* Stats */}
                <div className="grid grid-cols-3 gap-3 mb-5">
                  {
                    stats.map((stat, i) => (
                      <motion.div
                        key={i}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.8 + i * 0.1 }}
                        className="bg-card rounded-xl p-3 border border-border/50 shadow-sm"
                      >
                        <p className="text-[10px] text-muted-foreground mb-1"> {stat.label} </p>
                        <div className="flex items-end gap-2">
                          <span className="text-xl font-semibold"> {stat.value} </span>
                          <span className="text-[10px] text-green-600 mb-0.5"> {stat.change} </span>
                        </div>
                      </motion.div>
                    ))}
                </div>

                {/* Recent Call Activity */}
                <div className="bg-card rounded-xl border border-border/50 overflow-hidden shadow-sm">
                  <div className="px-4 py-2.5 border-b border-border/50 flex items-center justify-between">
                    <h3 className="font-medium text-sm">Recent Calls</h3>
                    <span className="text-[10px] text-muted-foreground bg-muted px-2 py-0.5 rounded-full">
                      5 handled
                    </span>
                  </div>
                  <div className="divide-y divide-border/30">
                    {
                      recentCalls.slice(0, 5).map((call, i) => (
                        <motion.div key={call.id} className="relative">
                          <motion.div
                            animate={{
                              backgroundColor: activeBooking === i ? "rgba(200, 180, 168, 0.15)" : "transparent",
                            }}
                            transition={{ duration: 0.3 }}
                            className="absolute inset-0"
                          />
                          <div className="relative px-4 py-2.5 flex items-center justify-between">
                            <div className="flex items-center gap-3">
                              <div className="w-7 h-7 rounded-full bg-accent/20 flex items-center justify-center text-xs font-medium">
                                {call.avatar}
                              </div>
                              <div>
                                <p className="text-xs font-medium">{call.caller}</p>
                                <p className="text-[10px] text-muted-foreground">{call.type}</p>
                              </div>
                            </div>
                            <div className="text-right">
                              <p className="text-xs">{call.time}</p>
                              <span
                                className={`text-[9px] px-1.5 py-0.5 rounded-full ${call.status === "synced"
                                  ? "bg-green-100 text-green-700"
                                  : call.status === "responded"
                                    ? "bg-blue-100 text-blue-700"
                                    : call.status === "forwarded"
                                      ? "bg-purple-100 text-purple-700"
                                      : "bg-amber-100 text-amber-700"
                                  }`}
                              >
                                {call.status}
                              </span>
                            </div>
                          </div>
                        </motion.div>
                      ))}
                  </div>
                </div>
              </div>
            </div>
          </MacBookMockup>
        </motion.div>

        {/* Voice Demo Modal Overlay */}
        <AnimatePresence>
          {isDemoOpen && (
            <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
              {/* Backdrop */}
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                onClick={() => setIsDemoOpen(false)}
                className="absolute inset-0 bg-black/60 backdrop-blur-sm"
              />

              {/* Modal */}
              <motion.div
                initial={{ opacity: 0, scale: 0.95, y: 20 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.95, y: 20 }}
                className="relative w-full max-w-md z-10"
              >
                <div className="absolute -top-12 right-0">
                  <button
                    onClick={() => setIsDemoOpen(false)}
                    className="text-white/50 hover:text-white transition-colors"
                  >
                    <X className="w-8 h-8" />
                  </button>
                </div>
                <VoiceDemoForm />
              </motion.div>
            </div>
          )}
        </AnimatePresence>

      </div >
    </section >
  )
}
