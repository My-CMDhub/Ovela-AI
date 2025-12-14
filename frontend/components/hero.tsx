"use client"

import type React from "react"

import { motion, useMotionValue, useSpring } from "framer-motion"
import Link from "next/link"
import { ArrowRight } from "lucide-react"
import { useState, useEffect } from "react"

const bookings = [
  { id: 1, client: "Sarah M.", service: "Gel Manicure", time: "10:00 AM", status: "confirmed", avatar: "S" },
  { id: 2, client: "Emma K.", service: "Lash Extensions", time: "11:30 AM", status: "pending", avatar: "E" },
  { id: 3, client: "Jessica L.", service: "Hair Color", time: "1:00 PM", status: "confirmed", avatar: "J" },
  { id: 4, client: "Amanda R.", service: "Pedicure", time: "2:30 PM", status: "confirmed", avatar: "A" },
  { id: 5, client: "Michelle T.", service: "Facial", time: "4:00 PM", status: "pending", avatar: "M" },
]

const stats = [
  { label: "Today's Bookings", value: "12", change: "+3" },
  { label: "Revenue", value: "$847", change: "+12%" },
  { label: "New Clients", value: "4", change: "+2" },
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

      {/* Subtle static orbs for depth */}
      <motion.div
        animate={{
          scale: [1, 1.05, 1],
          x: [0, 15, 0],
        }}
        transition={{ duration: 20, repeat: Infinity, ease: "easeInOut" }}
        className="absolute -top-40 -left-40 w-[500px] h-[500px] rounded-full"
        style={{
          background: "radial-gradient(circle, rgba(244,239,233,0.25) 0%, rgba(244,239,233,0.08) 50%, transparent 70%)",
          filter: "blur(35px)",
          willChange: "transform"
        }}
      />



      {Array.from({ length: 6 }).map((_, i) => (
        <motion.div
          key={i}
          className="absolute"
          style={{
            left: `${15 + ((i * 43) % 70)}%`,
            top: `${10 + ((i * 29) % 80)}%`,
          }}
          animate={{
            y: [0, -40 - (i % 3) * 20, 0],
            x: [0, i % 2 === 0 ? 15 : -15, 0],
            opacity: [0, 0.5, 0],
            scale: [0, 1, 0],
          }}
          transition={{
            duration: 8 + (i % 3) * 2,
            repeat: Infinity,
            delay: (i * 1.2) % 8,
            ease: "easeInOut",
          }}
        >
          {/* Sparkle/diamond shape */}
          <svg width={6 + (i % 2) * 3} height={6 + (i % 2) * 3} viewBox="0 0 10 10" className="text-accent">
            <path d="M5 0L6 4L10 5L6 6L5 10L4 6L0 5L4 4L5 0Z" fill="currentColor" fillOpacity={0.4} />
          </svg>
        </motion.div>
      ))}

      {Array.from({ length: 3 }).map((_, i) => (
        <motion.div
          key={`circle-${i}`}
          className="absolute rounded-full"
          style={{
            width: 12 + i * 6,
            height: 12 + i * 6,
            left: `${15 + ((i * 40) % 70)}%`,
            top: `${20 + ((i * 30) % 60)}%`,
            background: `radial-gradient(circle at 30% 30%, rgba(255,255,255,0.5), rgba(200,180,168,${0.15 + i * 0.08}))`,
            boxShadow: "0 2px 4px rgba(200,180,168,0.1)",
          }}
          animate={{
            y: [0, -40 - i * 10, 0],
            x: [0, i % 2 === 0 ? 10 : -10, 0],
            opacity: [0.2, 0.4, 0.2],
            scale: [0.9, 1.05, 0.9],
          }}
          transition={{
            duration: 12 + i * 3,
            repeat: Infinity,
            delay: i * 1.5,
            ease: "easeInOut",
          }}
        />
      ))}

      {/* Grid/Panel pattern revealed by orb light */}
      <motion.div
        style={{
          x: smoothX,
          y: smoothY,
        }}
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

export function Hero() {
  const [currentTime, setCurrentTime] = useState(new Date())
  const [activeBooking, setActiveBooking] = useState(0)

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000)
    return () => clearInterval(timer)
  }, [])

  useEffect(() => {
    const bookingTimer = setInterval(() => {
      setActiveBooking((prev) => (prev + 1) % bookings.length)
    }, 2500)
    return () => clearInterval(bookingTimer)
  }, [])

  return (
    <section className="relative min-h-screen flex items-center justify-center pt-20 pb-12 overflow-hidden">
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
            <span className="flex h-2 w-2 rounded-full bg-primary mr-2 animate-pulse"></span>
            Zero-Staff Overhead • 24/7 Availability
          </motion.div>

          {/* Main Heading */}
          <motion.h1
            variants={{
              hidden: { opacity: 0, y: 20, filter: "blur(10px)" },
              visible: { opacity: 1, y: 0, filter: "blur(0px)", transition: { duration: 0.8, ease: "easeOut" } }
            }}
            initial="hidden"
            animate="visible"
            className="mx-auto max-w-4xl font-serif text-5xl font-medium tracking-tight text-foreground sm:text-7xl"
          >
            The Receptionist That <br />
            <span className="italic text-muted-foreground">Never Sleeps.</span>
          </motion.h1>

          {/* Subtitle */}
          <motion.p
            variants={{
              hidden: { opacity: 0, y: 20, filter: "blur(8px)" },
              visible: { opacity: 1, y: 0, filter: "blur(0px)", transition: { duration: 0.8, delay: 0.2, ease: "easeOut" } }
            }}
            initial="hidden"
            animate="visible"
            className="mx-auto mt-6 max-w-2xl text-lg text-muted-foreground sm:text-xl"
          >
            Your website waits. <strong className="text-foreground font-medium">Our AI brings customers in.</strong> Turn missed calls into guaranteed revenue 24/7 without picking up the phone.
          </motion.p>

          {/* CTA Buttons */}
          <motion.div
            variants={{
              hidden: { opacity: 0, y: 20, filter: "blur(6px)" },
              visible: { opacity: 1, y: 0, filter: "blur(0px)", transition: { duration: 0.8, delay: 0.4, ease: "easeOut" } }
            }}
            initial="hidden"
            animate="visible"
            className="mt-8 flex flex-col items-center justify-center gap-4 sm:flex-row"
          >
            <Link
              href="#live-preview"
              className="inline-flex h-12 items-center justify-center rounded-full bg-primary px-8 text-base font-medium text-primary-foreground shadow transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50"
            >
              Start Automating
              <ArrowRight className="ml-2 h-4 w-4" />
            </Link>
            <Link
              href="#contact"
              className="inline-flex h-12 items-center justify-center rounded-full border border-input bg-background px-8 text-base font-medium shadow-sm transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50"
            >
              View Demo
            </Link>
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
                  app.Ovela.dev/dashboard
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
                    <span className="font-serif text-lg font-semibold">N</span>
                  </div>
                  <div>
                    <p className="font-semibold text-sm">GlowArt Studio</p>
                    <p className="text-xs text-muted-foreground">Pro Plan</p>
                  </div>
                </div>

                <nav className="space-y-1">
                  {[
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
                    <h2 className="text-base font-semibold">Good morning, Lisa</h2>
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
                  {stats.map((stat, i) => (
                    <motion.div
                      key={i}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: 0.8 + i * 0.1 }}
                      className="bg-card rounded-xl p-3 border border-border/50 shadow-sm"
                    >
                      <p className="text-[10px] text-muted-foreground mb-1">{stat.label}</p>
                      <div className="flex items-end gap-2">
                        <span className="text-xl font-semibold">{stat.value}</span>
                        <span className="text-[10px] text-green-600 mb-0.5">{stat.change}</span>
                      </div>
                    </motion.div>
                  ))}
                </div>

                {/* Today's Bookings */}
                <div className="bg-card rounded-xl border border-border/50 overflow-hidden shadow-sm">
                  <div className="px-4 py-2.5 border-b border-border/50 flex items-center justify-between">
                    <h3 className="font-medium text-sm">Today&apos;s Bookings</h3>
                    <span className="text-[10px] text-muted-foreground bg-muted px-2 py-0.5 rounded-full">
                      5 appointments
                    </span>
                  </div>
                  <div className="divide-y divide-border/30">
                    {bookings.slice(0, 5).map((booking, i) => (
                      <motion.div key={booking.id} className="relative">
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
                              {booking.avatar}
                            </div>
                            <div>
                              <p className="text-xs font-medium">{booking.client}</p>
                              <p className="text-[10px] text-muted-foreground">{booking.service}</p>
                            </div>
                          </div>
                          <div className="text-right">
                            <p className="text-xs">{booking.time}</p>
                            <span
                              className={`text-[9px] px-1.5 py-0.5 rounded-full ${booking.status === "confirmed"
                                ? "bg-green-100 text-green-700"
                                : "bg-amber-100 text-amber-700"
                                }`}
                            >
                              {booking.status}
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
      </div >
    </section >
  )
}
