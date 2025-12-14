"use client"

import type React from "react"

import { motion } from "framer-motion"
import { useState, useEffect } from "react"

const messages = [
  { type: "bot", text: "Hi! Welcome to GlowArt Nails. I'm Ovela, your booking assistant." },
  { type: "user", text: "Hi! Do you have any availability this Saturday?" },
  { type: "bot", text: "Let me check Saturday for you..." },
  {
    type: "bot",
    text: "Yes! Here are the available slots:\n\n• 10:00 AM\n• 11:30 AM\n• 2:00 PM\n• 4:30 PM\n\nWhat service would you like?",
  },
  { type: "user", text: "Gel manicure at 2pm please" },
  {
    type: "bot",
    text: "Perfect choice! I've booked you in for:\n\n📅 Saturday, Dec 7th\n⏰ 2:00 PM\n💅 Gel Manicure ($45)\n\nYou'll receive a reminder 24h before. See you soon!",
  },
]

function IPhoneMockup({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative">
      {/* Glow/shadow underneath */}
      <div className="absolute -inset-8 bg-gradient-to-b from-accent/5 via-transparent to-transparent rounded-[80px] blur-2xl -z-10" />
      <div className="absolute -bottom-12 left-1/2 -translate-x-1/2 w-2/3 h-16 bg-black/25 rounded-full blur-xl -z-10" />

      {/* Side Buttons - Left (Silent Switch & Volume) */}
      <div className="absolute -left-[2.5px] top-[90px] w-[3px] h-[28px] bg-gradient-to-r from-[#2a2a2c] to-[#3a3a3c] rounded-l-sm" />
      <div className="absolute -left-[2.5px] top-[135px] w-[3px] h-[50px] bg-gradient-to-r from-[#2a2a2c] to-[#3a3a3c] rounded-l-sm" />
      <div className="absolute -left-[2.5px] top-[195px] w-[3px] h-[50px] bg-gradient-to-r from-[#2a2a2c] to-[#3a3a3c] rounded-l-sm" />

      {/* Side Button - Right (Power) */}
      <div className="absolute -right-[2.5px] top-[155px] w-[3px] h-[70px] bg-gradient-to-l from-[#2a2a2c] to-[#3a3a3c] rounded-r-sm" />

      {/* Phone Frame - Titanium Natural finish */}
      <div
        className="relative rounded-[52px] p-[10px]"
        style={{
          background: "linear-gradient(135deg, #8a8a8e 0%, #6a6a6e 50%, #4a4a4e 100%)",
          boxShadow: `
            0 50px 100px -20px rgba(0,0,0,0.5),
            0 30px 60px -30px rgba(0,0,0,0.6),
            inset 0 1px 0 rgba(255,255,255,0.2),
            inset 0 -1px 0 rgba(0,0,0,0.3)
          `,
        }}
      >
        {/* Inner black bezel */}
        <div className="relative bg-black rounded-[44px] p-[2px]">
          {/* Screen */}
          <div
            className="relative bg-background rounded-[42px] overflow-hidden"
            style={{ width: "280px", height: "600px" }}
          >
            {/* Dynamic Island */}
            <div className="absolute top-3 left-1/2 -translate-x-1/2 z-49">
              <div
                className="bg-black rounded-full flex items-center justify-center"
                style={{ width: "110px", height: "34px" }}
              >
                {/* Face ID sensors (left side) */}
                <div className="absolute left-4 w-2 h-2 rounded-full bg-[#1a1a1a]" />
                {/* Camera (right side) */}
                <div className="absolute right-4 w-[10px] h-[10px] rounded-full bg-[#1a1a1a] ring-[1px] ring-[#2a2a2c]">
                  <div className="absolute inset-[2px] rounded-full bg-gradient-to-br from-[#2a4a6a] to-[#1a2a3a]" />
                  <div className="absolute top-[1px] left-[1px] w-[2px] h-[2px] rounded-full bg-white/30" />
                </div>
              </div>
            </div>

            {/* Screen Content */}
            <div className="h-full flex flex-col">{children}</div>

            {/* Home Indicator */}
            <div className="absolute bottom-2 left-1/2 -translate-x-1/2 w-[120px] h-[4px] bg-foreground/30 rounded-full" />
          </div>
        </div>
      </div>

      {/* Subtle reflection overlay */}
      <div className="absolute inset-0 rounded-[52px] bg-gradient-to-br from-white/10 via-transparent to-transparent pointer-events-none" />
    </div>
  )
}

function BatteryIcon({ percentage = 80 }: { percentage?: number }) {
  return (
    <div className="flex items-center gap-[1px]">
      {/* Battery body */}
      <div className="relative w-[22px] h-[11px] rounded-[3px] border-[1.5px] border-current flex items-center p-[2px]">
        {/* Battery level */}
        <div
          className={`h-full rounded-[1px] ${percentage > 20 ? "bg-current" : "bg-red-500"}`}
          style={{ width: `${percentage}%` }}
        />
      </div>
      {/* Battery cap */}
      <div className="w-[1.5px] h-[5px] bg-current rounded-r-sm opacity-60" />
    </div>
  )
}

export function LivePreview() {
  const [visibleMessages, setVisibleMessages] = useState<number>(0)
  const [isInView, setIsInView] = useState(false)

  useEffect(() => {
    if (!isInView) return

    const interval = setInterval(() => {
      setVisibleMessages((prev) => {
        if (prev < messages.length) return prev + 1
        return prev
      })
    }, 1200)

    return () => clearInterval(interval)
  }, [isInView])

  return (
    <section id="live-preview" className="py-32 px-6 bg-card">
      <div className="max-w-6xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, ease: "easeOut" }}
          className="text-center mb-16"
        >
          <h2 className="font-serif text-4xl md:text-5xl tracking-tight mb-4">See Ovela in action</h2>
          <p className="text-muted-foreground text-lg">A real booking conversation, automated end-to-end.</p>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 40 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.8, ease: "easeOut" }}
          onViewportEnter={() => setIsInView(true)}
          className="flex justify-center"
        >
          <IPhoneMockup>
            {/* Status Bar - iOS style */}
            <div className="flex items-center justify-between px-7 pt-[52px] pb-2 text-[13px] font-semibold">
              <span>9:41</span>
              <div className="flex items-center gap-1.5">
                {/* Cellular signal */}
                <svg className="w-[17px] h-[12px]" viewBox="0 0 17 12" fill="currentColor">
                  <rect x="0" y="7" width="3" height="5" rx="0.5" />
                  <rect x="4.5" y="5" width="3" height="7" rx="0.5" />
                  <rect x="9" y="2.5" width="3" height="9.5" rx="0.5" />
                  <rect x="13.5" y="0" width="3" height="12" rx="0.5" />
                </svg>
                {/* WiFi */}
                <svg className="w-[15px] h-[11px]" viewBox="0 0 15 11" fill="currentColor">
                  <path d="M7.5 2.5C5.5 2.5 3.7 3.2 2.3 4.4L1 3C2.7 1.5 5 0.5 7.5 0.5S12.3 1.5 14 3L12.7 4.4C11.3 3.2 9.5 2.5 7.5 2.5Z" />
                  <path d="M7.5 5.5C6.2 5.5 5 6 4.1 6.8L2.8 5.4C4 4.3 5.7 3.5 7.5 3.5S11 4.3 12.2 5.4L10.9 6.8C10 6 8.8 5.5 7.5 5.5Z" />
                  <path d="M7.5 8.5C6.8 8.5 6.2 8.8 5.8 9.2L7.5 11L9.2 9.2C8.8 8.8 8.2 8.5 7.5 8.5Z" />
                </svg>
                {/* Battery */}
                <BatteryIcon percentage={85} />
              </div>
            </div>

            {/* WhatsApp Header */}
            <div className="bg-accent/10 px-4 py-3 flex items-center gap-3 border-b border-border/30">
              <button className="p-1">
                <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <path d="M15 18l-6-6 6-6" />
                </svg>
              </button>
              <div className="w-9 h-9 rounded-full bg-accent/30 flex items-center justify-center text-sm font-semibold">
                G
              </div>
              <div className="flex-1">
                <p className="font-semibold text-sm">GlowArt Nails</p>
                <p className="text-xs text-muted-foreground">online</p>
              </div>
              <button className="p-2">
                <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z" />
                </svg>
              </button>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-3 space-y-3 bg-background">
              {/* Date Chip */}
              <div className="flex justify-center">
                <span className="text-xs text-muted-foreground bg-muted/50 px-3 py-1 rounded-full">Today</span>
              </div>

              {messages.slice(0, visibleMessages).map((message, index) => (
                <motion.div
                  key={index}
                  initial={{ opacity: 0, y: 15, scale: 0.95 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  transition={{ duration: 0.3, ease: "easeOut" }}
                  className={`flex ${message.type === "user" ? "justify-end" : "justify-start"}`}
                >
                  <div
                    className={`max-w-[80%] rounded-2xl px-3 py-2 relative ${message.type === "user" ? "bg-accent/25 rounded-br-md" : "bg-muted/70 rounded-bl-md"
                      }`}
                  >
                    <p className="text-[13px] leading-relaxed whitespace-pre-line">{message.text}</p>
                    <span className="text-[10px] text-muted-foreground mt-1 block text-right">
                      {message.type === "user" ? "9:41" : "9:41"}
                      {message.type === "user" && <span className="ml-1 text-accent">✓✓</span>}
                    </span>
                  </div>
                </motion.div>
              ))}

              {visibleMessages < messages.length && visibleMessages > 0 && (
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex justify-start">
                  <div className="bg-muted/70 rounded-2xl rounded-bl-md px-4 py-3">
                    <div className="flex gap-1">
                      {[0, 1, 2].map((i) => (
                        <motion.div
                          key={i}
                          animate={{ opacity: [0.4, 1, 0.4] }}
                          transition={{ duration: 0.8, repeat: Number.POSITIVE_INFINITY, delay: i * 0.15 }}
                          className="w-2 h-2 rounded-full bg-muted-foreground"
                        />
                      ))}
                    </div>
                  </div>
                </motion.div>
              )}
            </div>

            {/* Input Bar */}
            <div className="px-3 py-2 pb-8 bg-background border-t border-border/30">
              <div className="flex items-center gap-2">
                <button className="p-2 text-muted-foreground">
                  <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="10" />
                    <path d="M8 14s1.5 2 4 2 4-2 4-2" />
                    <line x1="9" y1="9" x2="9.01" y2="9" />
                    <line x1="15" y1="9" x2="15.01" y2="9" />
                  </svg>
                </button>
                <div className="flex-1 bg-muted/50 rounded-full px-4 py-2 text-sm text-muted-foreground">
                  Type a message
                </div>
                <button className="p-2 text-muted-foreground">
                  <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M12 15c1.66 0 3-1.34 3-3V6c0-1.66-1.34-3-3-3S9 4.34 9 6v6c0 1.66 1.34 3 3 3z" />
                    <path d="M17 12c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-2.08c3.39-.49 6-3.39 6-6.92h-2z" />
                  </svg>
                </button>
              </div>
            </div>
          </IPhoneMockup>
        </motion.div>

        {/* Caption */}
        <motion.p
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          transition={{ delay: 0.5 }}
          className="text-center text-sm text-muted-foreground mt-8"
        >
          Automated responses in under 3 seconds, 24/7
        </motion.p>
      </div>
    </section>
  )
}
