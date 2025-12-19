"use client"

import type React from "react"
import { motion, AnimatePresence } from "framer-motion"
import { useState, useEffect, useRef } from "react"

// Conversation transcript with timing - Real, emotionally engaging dialogue
const conversation = [
  { speaker: "ovela", text: "Hey there! Thanks for calling. This is Ovela - what can I help you with today?", duration: 3500 },
  { speaker: "user", text: "Oh hi! I've been trying to call all morning but kept getting voicemail...", duration: 3000 },
  { speaker: "ovela", text: "I'm so sorry about that! Well, you've got me now. What do you need?", duration: 3500 },
  { speaker: "user", text: "I need to reschedule my appointment for tomorrow. Something came up with my daughter's school.", duration: 4000 },
  { speaker: "ovela", text: "Of course, no worries at all! Let me find you a better time. How about Thursday at 2 PM?", duration: 4000 },
  { speaker: "user", text: "That would be perfect, thank you so much!", duration: 2000 },
  { speaker: "ovela", text: "All set! You'll get a text confirmation in just a sec. Anything else I can help with?", duration: 3500 },
  { speaker: "user", text: "No, that's it. You're a lifesaver!", duration: 2000 },
]

// Brand colors - consistent pinkish tones
const BRAND_GRADIENT = "linear-gradient(to bottom, #e8d5d0 0%, #dcc8c3 50%, #d4bdb8 100%)"
const BRAND_GRADIENT_ANSWERED = "linear-gradient(to bottom, #d4bdb8 0%, #c9b0ab 50%, #bfa5a0 100%)"

// iPhone-Style Split Waveform - Both colors visible, only active side animates
function SplitWaveform({
  currentSpeaker,
  isActive,
  currentText
}: {
  currentSpeaker: "ovela" | "user" | null
  isActive: boolean
  currentText?: string
}) {
  const bars = 6 // 6 bars per side

  // Calculate intensity based on text length (more words = more intense)
  const textIntensity = currentText ? Math.min(currentText.length / 50, 1.5) : 1

  const isIdle = currentSpeaker === null

  return (
    <div className="flex items-center gap-[1px] h-5">
      {/* Green side (Ovela) - Left */}
      <div className="flex items-center gap-[1.5px]">
        {Array.from({ length: bars }).map((_, i) => {
          const isOvelaActive = currentSpeaker === "ovela" && isActive
          const baseHeight = 3
          const maxHeight = 12 * textIntensity

          return (
            <motion.div
              key={`green-${i}`}
              className="w-[2px] rounded-full bg-green-400"
              animate={
                isIdle ? {
                  // Idle: subtle breathing animation
                  height: baseHeight + 1,
                  opacity: 1,
                } : isOvelaActive ? {
                  // Active: full animation with physics
                  height: [
                    baseHeight + Math.sin(i * 0.5) * 1,
                    maxHeight * (0.4 + Math.random() * 0.6),
                    baseHeight + Math.cos(i * 0.6) * 2,
                    maxHeight * (0.5 + Math.random() * 0.5),
                    baseHeight + Math.sin(i * 0.5) * 1,
                  ],
                  opacity: 1,
                } : {
                  height: baseHeight,
                  opacity: 1,
                }
              }
              transition={{
                duration: isOvelaActive ? 0.6 + (i % 3) * 0.1 : 0.3,
                repeat: isOvelaActive ? Infinity : 0,
                ease: "easeInOut",
                delay: i * 0.04,
              }}
            />
          )
        })}
      </div>

      {/* Orange side (User) - Right */}
      <div className="flex items-center gap-[1.5px]">
        {Array.from({ length: bars }).map((_, i) => {
          const isUserActive = currentSpeaker === "user" && isActive
          const baseHeight = 3
          const maxHeight = 12 * textIntensity

          // When idle, show green with yellow gradient at the end
          const colorClass = isIdle
            ? i >= bars - 2 ? "bg-yellow-400" : "bg-green-400"
            : "bg-orange-400"

          return (
            <motion.div
              key={`orange-${i}`}
              className={`w-[2px] rounded-full ${colorClass}`}
              animate={
                isIdle ? {
                  // Idle: subtle breathing, green with yellow gradient
                  height: baseHeight + 1,
                  opacity: i >= bars - 2 ? 0.8 : 1, // Yellow bars slightly dimmer for gradient effect
                } : isUserActive ? {
                  // Active: full animation with physics
                  height: [
                    baseHeight + Math.sin(i * 0.5) * 1,
                    maxHeight * (0.4 + Math.random() * 0.6),
                    baseHeight + Math.cos(i * 0.6) * 2,
                    maxHeight * (0.5 + Math.random() * 0.5),
                    baseHeight + Math.sin(i * 0.5) * 1,
                  ],
                  opacity: 1,
                } : {
                  // Inactive: static, full visibility
                  height: baseHeight,
                  opacity: 1,
                }
              }
              transition={{
                duration: isUserActive ? 0.6 + (i % 3) * 0.1 : 0.3,
                repeat: isUserActive ? Infinity : 0,
                ease: "easeInOut",
                delay: i * 0.04,
              }}
            />
          )
        })}
      </div>
    </div>
  )
}

// Compact Dynamic Island with call info
function DynamicIsland({
  isAnswered,
  callTime,
  currentSpeaker,
  currentText
}: {
  isAnswered: boolean
  callTime: number
  currentSpeaker: "ovela" | "user" | null
  currentText?: string
}) {
  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  return (
    <motion.div
      className="absolute top-[10px] left-1/2 -translate-x-1/2 z-26"
      animate={{
        width: isAnswered ? 155 : 100,
        height: isAnswered ? 30 : 28,
      }}
      transition={{ duration: 0.4, ease: [0.32, 0.72, 0, 1] }}
    >
      <div className="bg-black rounded-full h-full w-full flex items-center justify-between px-2.5 overflow-hidden">
        {isAnswered ? (
          <>
            <div className="flex items-center gap-1.5">
              <svg className="w-3.5 h-3.5 text-green-400" fill="currentColor" viewBox="0 0 24 24">
                <path d="M6.62 10.79c1.44 2.83 3.76 5.14 6.59 6.59l2.2-2.2c.27-.27.67-.36 1.02-.24 1.12.37 2.33.57 3.57.57.55 0 1 .45 1 1V20c0 .55-.45 1-1 1-9.39 0-17-7.61-17-17 0-.55.45-1 1-1h3.5c.55 0 1 .45 1 1 0 1.25.2 2.45.57 3.57.11.35.03.74-.25 1.02l-2.2 2.2z" />
              </svg>
              <span className="text-green-400 text-[10px] font-medium tabular-nums">{formatTime(callTime)}</span>
            </div>

            <motion.div
              className="w-[4px] h-[4px] rounded-full bg-yellow-400"
              animate={{ opacity: [1, 0.4, 1] }}
              transition={{ duration: 1.2, repeat: Infinity, ease: "easeInOut" }}
            />

            <SplitWaveform
              currentSpeaker={currentSpeaker}
              isActive={currentSpeaker !== null}
              currentText={currentText}
            />
          </>
        ) : (
          <>
            <div className="absolute left-3 w-2 h-2 rounded-full bg-[#1a1a1a]" />
            <div className="absolute right-3 w-[9px] h-[9px] rounded-full bg-[#1a1a1a] ring-[1px] ring-[#2a2a2c]">
              <div className="absolute inset-[2px] rounded-full bg-gradient-to-br from-[#2a4a6a] to-[#1a2a3a]" />
            </div>
          </>
        )}
      </div>
    </motion.div>
  )
}

// Glassmorphism Call Button with proper spacing
function CallButton({ icon, label, isEnd = false }: { icon: React.ReactNode; label: string; isEnd?: boolean }) {
  return (
    <button className="flex flex-col items-center gap-2 active:scale-95 transition-transform">
      <div className={`w-[54px] h-[54px] rounded-full flex items-center justify-center shadow-lg ${isEnd ? "bg-red-500" : "bg-white/25 backdrop-blur-md border border-white/15"
        }`}>
        {icon}
      </div>
      <span className="text-white/90 text-[11px] font-medium tracking-wide">{label}</span>
    </button>
  )
}

// External Floating Transcript with Speaker Label - Theme Adaptive & Responsive
function ExternalTranscript({ text, speaker, isVisible }: { text: string; speaker: "ovela" | "user"; isVisible: boolean }) {
  const isOvela = speaker === "ovela"

  return (
    <AnimatePresence mode="wait">
      {isVisible && (
        <motion.div
          key={text}
          initial={{ opacity: 0, y: 15, scale: 0.95 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: -10, scale: 0.95 }}
          transition={{ duration: 0.35, ease: "easeOut" }}
          className={`absolute max-w-[170px] md:max-w-none md:w-[300px] z-30 ${isOvela
            ? 'top-[60px] left-[10px] md:top-1/2 md:-translate-y-1/2 md:right-[calc(100%+20px)] md:left-auto'
            : 'top-[60px] right-[10px] md:top-1/2 md:-translate-y-1/2 md:left-[calc(100%+20px)] md:right-auto'
            }`}
        >
          <div className={`text-[9px] font-bold uppercase tracking-widest mb-1 ${isOvela ? 'text-green-500 dark:text-green-400 text-left md:text-right' : 'text-orange-500 dark:text-orange-400 text-right md:text-left'
            }`}>
            {isOvela ? 'Ovela' : 'Customer'}
          </div>

          <div className={`px-3.5 py-2.5 rounded-2xl backdrop-blur-sm shadow-lg border ${isOvela
            ? 'bg-green-500/15 dark:bg-green-500/20 border-green-400/25 dark:border-green-400/30 rounded-br-sm'
            : 'bg-orange-500/15 dark:bg-orange-500/20 border-orange-400/25 dark:border-orange-400/30 rounded-bl-sm'
            }`}>
            <p className={`text-[11px] md:text-[13px] leading-relaxed ${isOvela ? 'text-green-900 dark:text-green-50' : 'text-orange-900 dark:text-orange-50'
              }`}>
              {text}
            </p>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

function IPhoneMockup({ children, dynamicIsland, ovelaTranscript, userTranscript }: {
  children: React.ReactNode
  dynamicIsland?: React.ReactNode
  ovelaTranscript?: { text: string; visible: boolean }
  userTranscript?: { text: string; visible: boolean }
}) {
  return (
    <div className="relative">
      {ovelaTranscript && <ExternalTranscript text={ovelaTranscript.text} speaker="ovela" isVisible={ovelaTranscript.visible} />}
      {userTranscript && <ExternalTranscript text={userTranscript.text} speaker="user" isVisible={userTranscript.visible} />}

      <div className="absolute -inset-8 bg-gradient-to-b from-accent/5 via-transparent to-transparent rounded-[80px] blur-2xl -z-10" />
      <div className="absolute -bottom-12 left-1/2 -translate-x-1/2 w-2/3 h-16 bg-black/25 rounded-full blur-xl -z-10" />

      {/* Side Buttons - Clearly visible, matching frame */}
      <div className="absolute -left-[2.5px] top-[90px] w-[3px] h-[28px] bg-gradient-to-r from-[#2a2a2c] to-[#3a3a3c] dark:from-foreground/40 dark:to-foreground/60 rounded-l-sm" />
      <div className="absolute -left-[2.5px] top-[135px] w-[3px] h-[50px] bg-gradient-to-r from-[#2a2a2c] to-[#3a3a3c] dark:from-foreground/40 dark:to-foreground/60 rounded-l-sm" />
      <div className="absolute -left-[2.5px] top-[195px] w-[3px] h-[50px] bg-gradient-to-r from-[#2a2a2c] to-[#3a3a3c] dark:from-foreground/40 dark:to-foreground/60 rounded-l-sm" />
      <div className="absolute -right-[2.5px] top-[155px] w-[3px] h-[70px] bg-gradient-to-l from-[#2a2a2c] to-[#3a3a3c] dark:from-foreground/40 dark:to-foreground/60 rounded-r-sm" />

      {/* Phone Frame - Black in light mode, lighter in dark mode */}
      <div
        className="relative rounded-[52px] p-[10px] bg-gradient-to-br from-[#1a1a1a] via-[#0a0a0a] to-[#1a1a1a] dark:from-foreground/60 dark:via-foreground/50 dark:to-foreground/60"
        style={{
          boxShadow: "0 50px 100px -20px rgba(0,0,0,0.5), 0 30px 60px -30px rgba(0,0,0,0.6), inset 0 1px 0 rgba(255,255,255,0.1), inset 0 -1px 0 rgba(0,0,0,0.3)",
        }}
      >
        <div className="relative bg-black rounded-[44px] p-[2px]">
          <div className="relative bg-background rounded-[42px] overflow-hidden" style={{ width: "280px", height: "600px" }}>
            {dynamicIsland}
            <div className="h-full flex flex-col">{children}</div>
            <div className="absolute bottom-2 left-1/2 -translate-x-1/2 w-[120px] h-[4px] bg-foreground/30 rounded-full" />
          </div>
        </div>
      </div>

      <div className="absolute inset-0 rounded-[52px] bg-gradient-to-br from-white/10 via-transparent to-transparent pointer-events-none" />
    </div>
  )
}

function BatteryIcon({ percentage = 80, dark = false }: { percentage?: number; dark?: boolean }) {
  return (
    <div className="flex items-center gap-[1px]">
      <div className={`relative w-[22px] h-[11px] rounded-[3px] border-[1.5px] ${dark ? 'border-black/70' : 'border-current'} flex items-center p-[2px]`}>
        <div className={`h-full rounded-[1px] ${percentage > 20 ? (dark ? "bg-black/70" : "bg-current") : "bg-red-500"}`} style={{ width: `${percentage}%` }} />
      </div>
      <div className={`w-[1.5px] h-[5px] ${dark ? 'bg-black/50' : 'bg-current'} rounded-r-sm opacity-60`} />
    </div>
  )
}

// Consistent OVELA text component
function OvelaText() {
  return (
    <div className="absolute top-[70px] left-0 right-0 text-center z-10 px-4">
      <div
        className="font-serif font-bold text-[65px] leading-none tracking-tight"
        style={{
          background: "linear-gradient(to bottom, #3a3a3a 0%, #3a3a3a 50%, rgba(58,58,58,0.3) 80%, rgba(58,58,58,0) 100%)",
          WebkitBackgroundClip: "text",
          WebkitTextFillColor: "transparent",
          backgroundClip: "text",
        }}
      >
        OVELA
      </div>
    </div>
  )
}

// Consistent Memoji size/position for both screens
const MEMOJI_SIZE = "w-[220px] h-[220px]"
const MEMOJI_POSITION = "top-[160px]"
const MEMOJI_SCALE = 2

export function LivePreview() {
  const [callPhase, setCallPhase] = useState<"ringing" | "sliding" | "answered" | "ending">("ringing")
  const [callTime, setCallTime] = useState(0)
  const [currentSpeaker, setCurrentSpeaker] = useState<"ovela" | "user" | null>(null)
  const [currentText, setCurrentText] = useState<string>("")
  const [ovelaTranscript, setOvelaTranscript] = useState<{ text: string; visible: boolean }>({ text: "", visible: false })
  const [userTranscript, setUserTranscript] = useState<{ text: string; visible: boolean }>({ text: "", visible: false })
  const [isInView, setIsInView] = useState(false)
  const conversationRef = useRef<NodeJS.Timeout | null>(null)

  // Full animation loop: ringing → answered → end → back to ringing
  useEffect(() => {
    if (!isInView) return

    const startLoop = () => {
      setCallPhase("ringing")
      setCallTime(0)
      setCurrentSpeaker(null)
      setOvelaTranscript({ text: "", visible: false })
      setUserTranscript({ text: "", visible: false })

      setTimeout(() => {
        setCallPhase("sliding")
        setTimeout(() => setCallPhase("answered"), 700)
      }, 2500)
    }

    startLoop()
  }, [isInView])

  // Call timer
  useEffect(() => {
    if (callPhase !== "answered") return

    const timer = setInterval(() => {
      setCallTime(prev => prev + 1)
    }, 1000)

    return () => clearInterval(timer)
  }, [callPhase])

  // Conversation progression with full loop
  useEffect(() => {
    if (callPhase !== "answered") return

    let messageIndex = 0

    const playNextMessage = () => {
      if (messageIndex >= conversation.length) {
        setCurrentSpeaker(null)
        setOvelaTranscript({ text: "", visible: false })
        setUserTranscript({ text: "", visible: false })

        setTimeout(() => {
          setCallPhase("ending")

          setTimeout(() => {
            setCallPhase("ringing")
            setCallTime(0)

            setTimeout(() => {
              setCallPhase("sliding")
              setTimeout(() => setCallPhase("answered"), 700)
            }, 2500)
          }, 500)
        }, 2000)
        return
      }

      const msg = conversation[messageIndex]
      setCurrentSpeaker(msg.speaker as "ovela" | "user")
      setCurrentText(msg.text)

      if (msg.speaker === "ovela") {
        setUserTranscript({ text: "", visible: false })
        setOvelaTranscript({ text: msg.text, visible: true })
      } else {
        setOvelaTranscript({ text: "", visible: false })
        setUserTranscript({ text: msg.text, visible: true })
      }

      conversationRef.current = setTimeout(() => {
        messageIndex++
        playNextMessage()
      }, msg.duration)
    }

    const startDelay = setTimeout(playNextMessage, 800)

    return () => {
      clearTimeout(startDelay)
      if (conversationRef.current) clearTimeout(conversationRef.current)
    }
  }, [callPhase])

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
          <h2 className="font-serif text-4xl md:text-5xl tracking-tight mb-4">Hear Ovela in action</h2>
          <p className="text-muted-foreground text-lg">A real call, handled automatically from start to finish.</p>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 40 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.8, ease: "easeOut" }}
          onViewportEnter={() => setIsInView(true)}
          className="flex justify-center"
        >
          <IPhoneMockup
            dynamicIsland={<DynamicIsland isAnswered={callPhase === "answered"} callTime={callTime} currentSpeaker={currentSpeaker} currentText={currentText} />}
            ovelaTranscript={ovelaTranscript}
            userTranscript={userTranscript}
          >
            <AnimatePresence mode="wait">
              {(callPhase === "ringing" || callPhase === "sliding") && (
                <motion.div
                  key="ringing"
                  initial={{ opacity: 1 }}
                  exit={{ opacity: 0, scale: 1.02 }}
                  transition={{ duration: 0.35 }}
                  className="absolute inset-0"
                >
                  <div className="absolute inset-0 rounded-[42px]" style={{ background: BRAND_GRADIENT }} />

                  {/* Status Bar - Parallel to Dynamic Island */}
                  <div className="relative flex items-center justify-between px-7 pt-[12px] pb-2 text-[13px] font-semibold text-black/75 z-30">
                    <span>9:41</span>
                    <div className="flex items-center gap-1.5">
                      <svg className="w-[17px] h-[12px]" viewBox="0 0 17 12" fill="currentColor">
                        <rect x="0" y="7" width="3" height="5" rx="0.5" />
                        <rect x="4.5" y="5" width="3" height="7" rx="0.5" />
                        <rect x="9" y="2.5" width="3" height="9.5" rx="0.5" />
                        <rect x="13.5" y="0" width="3" height="12" rx="0.5" />
                      </svg>
                      <BatteryIcon percentage={85} dark />
                    </div>
                  </div>

                  {/* OVELA Text - Consistent */}
                  <OvelaText />

                  {/* Memoji - Consistent size/position */}
                  <motion.div
                    className={`absolute ${MEMOJI_POSITION} left-1/2 -translate-x-1/2 z-20`}
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: MEMOJI_SCALE }}
                    transition={{ duration: 0.6, delay: 0.15 }}
                  >
                    <img src="/IMemoji-ovela.png" alt="Ovela AI" className={`${MEMOJI_SIZE} object-contain drop-shadow-[0_20px_40px_rgba(0,0,0,0.25)]`} />
                  </motion.div>

                  {/* Ringing Buttons */}
                  <div className="absolute bottom-[125px] left-0 right-0 flex justify-around px-10 z-30">
                    <button className="flex flex-col items-center gap-2">
                      <div className="w-12 h-12 bg-white/35 backdrop-blur-md rounded-full flex items-center justify-center shadow-lg border border-white/20">
                        <svg className="w-5 h-5 text-white" fill="currentColor" viewBox="0 0 24 24">
                          <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H6l-2 2V4h16v12z" />
                        </svg>
                      </div>
                      <span className="text-white/90 text-[11px] font-medium drop-shadow-sm">Message</span>
                    </button>

                    <button className="flex flex-col items-center gap-2">
                      <div className="w-12 h-12 bg-white/35 backdrop-blur-md rounded-full flex items-center justify-center shadow-lg border border-white/20">
                        <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                      </div>
                      <span className="text-white/90 text-[11px] font-medium drop-shadow-sm">Remind Me</span>
                    </button>
                  </div>

                  {/* Slide to Answer */}
                  <div className="absolute bottom-[52px] left-5 right-5 z-30">
                    <div className="relative h-[50px] bg-white/30 backdrop-blur-md rounded-full flex items-center px-1.5 shadow-lg border border-white/20">
                      <motion.div
                        className="absolute w-[44px] h-[44px] bg-white rounded-full flex items-center justify-center shadow-lg"
                        animate={callPhase === "sliding" ? { x: 195, opacity: 0 } : { x: [0, 10, 0] }}
                        transition={callPhase === "sliding" ? { duration: 0.5, ease: "easeIn" } : { duration: 2.2, repeat: Infinity, ease: "easeInOut" }}
                      >
                        <svg className="w-5 h-5 text-green-500" fill="currentColor" viewBox="0 0 24 24">
                          <path d="M6.62 10.79c1.44 2.83 3.76 5.14 6.59 6.59l2.2-2.2c.27-.27.67-.36 1.02-.24 1.12.37 2.33.57 3.57.57.55 0 1 .45 1 1V20c0 .55-.45 1-1 1-9.39 0-17-7.61-17-17 0-.55.45-1 1-1h3.5c.55 0 1 .45 1 1 0 1.25.2 2.45.57 3.57.11.35.03.74-.25 1.02l-2.2 2.2z" />
                        </svg>
                      </motion.div>
                      <div className="flex-1 text-center pl-8">
                        <span className="text-white/95 text-[14px] font-medium drop-shadow-sm">slide to answer</span>
                      </div>
                    </div>
                  </div>
                </motion.div>
              )}

              {(callPhase === "answered" || callPhase === "ending") && (
                <motion.div
                  key="answered"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: callPhase === "ending" ? 0 : 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.35 }}
                  className="absolute inset-0"
                >
                  <div className="absolute inset-0 rounded-[42px]" style={{ background: BRAND_GRADIENT_ANSWERED }} />

                  {/* Status Bar - Parallel to Dynamic Island */}
                  <div className="relative flex items-center justify-between px-7 pt-[12px] pb-2 text-[13px] font-semibold text-black/70 z-30">
                    <span>9:41</span>
                    <div className="flex items-center gap-1.5">
                      <svg className="w-[17px] h-[12px]" viewBox="0 0 17 12" fill="currentColor">
                        <rect x="0" y="7" width="3" height="5" rx="0.5" />
                        <rect x="4.5" y="5" width="3" height="7" rx="0.5" />
                        <rect x="9" y="2.5" width="3" height="9.5" rx="0.5" />
                        <rect x="13.5" y="0" width="3" height="12" rx="0.5" />
                      </svg>
                      <BatteryIcon percentage={85} dark />
                    </div>
                  </div>

                  {/* OVELA Text - Same as ringing screen */}
                  <OvelaText />

                  {/* Memoji - Same size/position as ringing */}
                  <motion.div
                    className={`absolute ${MEMOJI_POSITION} left-1/2 -translate-x-1/2 z-20`}
                    initial={{ scale: MEMOJI_SCALE * 0.9, opacity: 0 }}
                    animate={{ scale: MEMOJI_SCALE, opacity: 1 }}
                    transition={{ duration: 0.4 }}
                  >
                    <img src="/IMemoji-ovela.png" alt="Ovela AI" className={`${MEMOJI_SIZE} object-contain drop-shadow-[0_20px_40px_rgba(0,0,0,0.25)]`} />
                  </motion.div>

                  {/* Call Controls - Row 1 with proper spacing */}
                  <div className="absolute bottom-[115px] left-0 right-0 flex justify-around px-8 z-30">
                    <CallButton icon={<svg className="w-6 h-6 text-white" fill="currentColor" viewBox="0 0 24 24"><path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z" /></svg>} label="speaker" />
                    <CallButton icon={<svg className="w-6 h-6 text-white" fill="currentColor" viewBox="0 0 24 24"><path d="M17 10.5V7c0-.55-.45-1-1-1H4c-.55 0-1 .45-1 1v10c0 .55.45 1 1 1h12c.55 0 1-.45 1-1v-3.5l4 4v-11l-4 4z" /></svg>} label="FaceTime" />
                    <CallButton icon={<svg className="w-6 h-6 text-white" fill="currentColor" viewBox="0 0 24 24"><path d="M19 11h-1.7c0 .74-.16 1.43-.43 2.05l1.23 1.23c.56-.98.9-2.09.9-3.28zm-4.02.17c0-.06.02-.11.02-.17V5c0-1.66-1.34-3-3-3S9 3.34 9 5v.18l5.98 5.99zM4.27 3L3 4.27l6.01 6.01V11c0 1.66 1.33 3 2.99 3 .22 0 .44-.03.65-.08l1.66 1.66c-.71.33-1.5.52-2.31.52-2.76 0-5.3-2.1-5.3-5.1H5c0 3.41 2.72 6.23 6 6.72V21h2v-3.28c.91-.13 1.77-.45 2.54-.9L19.73 21 21 19.73 4.27 3z" /></svg>} label="mute" />
                  </div>

                  {/* Call Controls - Row 2 with proper spacing */}
                  <div className="absolute bottom-[32px] left-0 right-0 flex justify-around px-8 z-30">
                    <CallButton icon={<svg className="w-5 h-5 text-white" fill="currentColor" viewBox="0 0 24 24"><circle cx="12" cy="12" r="2" /><circle cx="6" cy="12" r="2" /><circle cx="18" cy="12" r="2" /></svg>} label="more" />
                    <CallButton icon={<svg className="w-6 h-6 text-white rotate-[135deg]" fill="currentColor" viewBox="0 0 24 24"><path d="M6.62 10.79c1.44 2.83 3.76 5.14 6.59 6.59l2.2-2.2c.27-.27.67-.36 1.02-.24 1.12.37 2.33.57 3.57.57.55 0 1 .45 1 1V20c0 .55-.45 1-1 1-9.39 0-17-7.61-17-17 0-.55.45-1 1-1h3.5c.55 0 1 .45 1 1 0 1.25.2 2.45.57 3.57.11.35.03.74-.25 1.02l-2.2 2.2z" /></svg>} label="End" isEnd />
                    <CallButton icon={<div className="grid grid-cols-3 gap-1">{[...Array(9)].map((_, i) => <div key={i} className="w-1.5 h-1.5 rounded-full bg-white" />)}</div>} label="keypad" />
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </IPhoneMockup>
        </motion.div>

        <motion.p
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          transition={{ delay: 0.5 }}
          className="text-center text-sm text-muted-foreground mt-8"
        >
          AI-powered calls answered in under 2 seconds, 24/7
        </motion.p>
      </div>
    </section>
  )
}
