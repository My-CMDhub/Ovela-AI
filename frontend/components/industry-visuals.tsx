"use client"

import { motion, AnimatePresence } from "framer-motion"
import { Check, Clock, HeartPulse, Key, Lock, MessageSquare, ShieldCheck, User, Volume2, Wifi } from "lucide-react"
import { useState, useEffect } from "react"

// Enhanced Minimalist Container
function LiveCard({ children, title, status = "Active" }: { children: React.ReactNode, title: string, status?: string }) {
    return (
        <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            whileInView={{ opacity: 1, y: 0, scale: 1 }}
            viewport={{ once: true, margin: "-50px" }}
            transition={{ duration: 0.8, ease: "easeOut" }}
            className="relative w-full max-w-md md:max-w-lg mx-auto perspective-1000"
        >
            {/* Ambient Glow - Pulse Effect */}
            <motion.div
                animate={{ opacity: [0.4, 0.6, 0.4], scale: [0.98, 1.02, 0.98] }}
                transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
                className="absolute -inset-1 bg-gradient-to-tr from-primary/10 via-primary/5 to-transparent rounded-[20px] blur-2xl -z-10"
            />

            {/* Glass Card */}
            <div className="bg-background/60 backdrop-blur-xl border border-border/50 rounded-2xl overflow-hidden shadow-2xl ring-1 ring-white/10 dark:ring-white/5">
                {/* Header */}
                <div className="px-5 py-4 border-b border-border/40 flex items-center justify-between bg-muted/20">
                    <div className="flex items-center gap-3">
                        <div className="flex gap-1.5">
                            <span className="w-2.5 h-2.5 rounded-full bg-red-500/20 border border-red-500/50" />
                            <span className="w-2.5 h-2.5 rounded-full bg-amber-500/20 border border-amber-500/50" />
                            <span className="w-2.5 h-2.5 rounded-full bg-green-500/20 border border-green-500/50" />
                        </div>
                        <div className="h-4 w-px bg-border/60 mx-1" />
                        <span className="text-[10px] font-mono font-medium text-muted-foreground uppercase tracking-widest">{title}</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <span className="relative flex h-2 w-2">
                            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                            <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
                        </span>
                        <span className="text-[10px] font-medium text-green-500">{status}</span>
                    </div>
                </div>

                {/* Content */}
                <div className="p-6 relative overflow-hidden">
                    {/* Scanline Effect */}
                    <div className="absolute inset-0 bg-[linear-gradient(to_bottom,transparent_50%,rgba(0,0,0,0.02)_50%)] bg-[length:100%_4px] pointer-events-none" />
                    {children}
                </div>
            </div>
        </motion.div>
    )
}

// Visual 1: Motel Night Mode - Animated Conversation
export function MotelVisual() {
    const [step, setStep] = useState(0)

    useEffect(() => {
        const timer1 = setTimeout(() => setStep(1), 1000) // Guest message
        const timer2 = setTimeout(() => setStep(2), 2500) // Typing...
        const timer3 = setTimeout(() => setStep(3), 4500) // Response

        return () => { clearTimeout(timer1); clearTimeout(timer2); clearTimeout(timer3) }
    }, [])

    return (
        <LiveCard title="Night Audit Protocol">
            <div className="space-y-6 font-sans relative z-10 min-h-[140px]">
                <AnimatePresence>
                    {step >= 1 && (
                        <motion.div
                            initial={{ opacity: 0, x: -10, y: 10 }}
                            animate={{ opacity: 1, x: 0, y: 0 }}
                            className="flex flex-col items-start gap-1.5"
                        >
                            <div className="text-[10px] text-muted-foreground ml-1">Guest • 2:04 AM</div>
                            <div className="bg-muted px-4 py-3 rounded-2xl rounded-tl-sm text-sm border border-border/40 shadow-sm max-w-[85%]">
                                Checking in late. Is the desk open?
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>

                <AnimatePresence mode="wait">
                    {step === 2 && (
                        <motion.div
                            initial={{ opacity: 0, scale: 0.9 }}
                            animate={{ opacity: 1, scale: 1 }}
                            exit={{ opacity: 0, scale: 0.9 }}
                            className="flex flex-col items-end gap-1.5"
                        >
                            <div className="text-[10px] text-muted-foreground mr-1">Ovela AI</div>
                            <div className="bg-primary/5 px-4 py-3 rounded-2xl rounded-tr-sm text-sm border border-primary/10 w-fit">
                                <div className="flex gap-1">
                                    <motion.span animate={{ opacity: [0.4, 1, 0.4] }} transition={{ repeat: Infinity, duration: 1.5, delay: 0 }} className="w-1.5 h-1.5 bg-primary/40 rounded-full" />
                                    <motion.span animate={{ opacity: [0.4, 1, 0.4] }} transition={{ repeat: Infinity, duration: 1.5, delay: 0.2 }} className="w-1.5 h-1.5 bg-primary/40 rounded-full" />
                                    <motion.span animate={{ opacity: [0.4, 1, 0.4] }} transition={{ repeat: Infinity, duration: 1.5, delay: 0.4 }} className="w-1.5 h-1.5 bg-primary/40 rounded-full" />
                                </div>
                            </div>
                        </motion.div>
                    )}

                    {step >= 3 && (
                        <motion.div
                            initial={{ opacity: 0, x: 10, y: 10 }}
                            animate={{ opacity: 1, x: 0, y: 0 }}
                            className="flex flex-col items-end gap-1.5"
                        >
                            <div className="text-[10px] text-muted-foreground mr-1">Ovela AI • 2:04 AM</div>
                            <div className="bg-primary/5 text-foreground p-1 rounded-2xl rounded-tr-sm text-sm border border-primary/10 w-full shadow-sm overflow-hidden">
                                <div className="px-3 py-2 text-sm">Reception is closed, but here is your digital key.</div>
                                <motion.div
                                    initial={{ y: 20, opacity: 0 }}
                                    animate={{ y: 0, opacity: 1 }}
                                    transition={{ delay: 0.3 }}
                                    className="bg-background rounded-xl p-2.5 mx-1 mb-1 border border-border/50 flex items-center justify-between gap-3 shadow-inner"
                                >
                                    <div className="flex items-center gap-3">
                                        <div className="bg-primary/10 p-2 rounded-lg">
                                            <Key className="w-4 h-4 text-primary" />
                                        </div>
                                        <div>
                                            <div className="text-[9px] text-muted-foreground uppercase tracking-wider">Room 204</div>
                                            <div className="font-mono text-base font-semibold tracking-widest">8291</div>
                                        </div>
                                    </div>
                                    <Lock className="w-4 h-4 text-green-500" />
                                </motion.div>
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>
        </LiveCard>
    )
}

// Visual 2: Dental Triage - Live Alert
export function DentalVisual() {
    const [progress, setProgress] = useState(0)

    useEffect(() => {
        const timer = setTimeout(() => setProgress(1), 1500)
        return () => clearTimeout(timer)
    }, [])

    return (
        <LiveCard title="Triage Agent" status="Monitoring">
            <div className="space-y-4">
                {/* Status Bar */}
                <div className="flex items-center justify-between bg-red-500/5 p-3 rounded-lg border border-red-500/10">
                    <div className="flex items-center gap-2">
                        <HeartPulse className="w-4 h-4 text-red-500 animate-pulse" />
                        <span className="text-xs font-bold text-red-500 uppercase tracking-wide">Emergency Detected</span>
                    </div>
                </div>

                <div className="space-y-3">
                    <div className="bg-card rounded-xl p-4 border border-border/50 shadow-sm relative overflow-hidden">
                        <div className="absolute left-0 top-0 bottom-0 w-1 bg-red-500" />
                        <div className="flex items-start gap-3">
                            <div className="p-2 bg-muted rounded-full">
                                <User className="w-4 h-4 text-foreground" />
                            </div>
                            <div>
                                <div className="text-sm font-medium">Broken Molar</div>
                                <div className="text-xs text-muted-foreground mt-0.5">Patient reporting severe pain (8/10).</div>
                            </div>
                        </div>
                    </div>

                    <div className="relative">
                        <AnimatePresence mode="wait">
                            {progress === 0 ? (
                                <motion.div
                                    key="searching"
                                    initial={{ opacity: 0 }}
                                    animate={{ opacity: 1 }}
                                    exit={{ opacity: 0 }}
                                    className="flex items-center justify-center py-4 text-xs text-muted-foreground gap-2"
                                >
                                    <Clock className="w-3 h-3 animate-spin" />
                                    Finding emergency slot...
                                </motion.div>
                            ) : (
                                <motion.div
                                    key="found"
                                    initial={{ opacity: 0, y: 10 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    className="bg-primary/5 rounded-xl p-3 border border-primary/10 flex items-center justify-between"
                                >
                                    <div className="flex items-center gap-3">
                                        <div className="bg-background p-2 rounded-lg shadow-sm border border-border/50">
                                            <CalendarIcon />
                                        </div>
                                        <div>
                                            <div className="text-xs font-semibold text-primary">Priority Slot Blocked</div>
                                            <div className="text-[10px] text-muted-foreground">Today, 2:15 PM</div>
                                        </div>
                                    </div>
                                    <div className="px-2 py-1 bg-background rounded-md text-[10px] font-bold border border-border/50 shadow-sm flex items-center gap-1">
                                        <Check className="w-3 h-3 text-primary" />
                                        AUTO-BOOKED
                                    </div>
                                </motion.div>
                            )}
                        </AnimatePresence>
                    </div>
                </div>
            </div>
        </LiveCard>
    )
}

function CalendarIcon() {
    return (
        <svg className="w-4 h-4 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
        </svg>
    )
}

// Visual 3: Physio Intake - Live Form Fill
export function PhysioVisual() {
    return (
        <LiveCard title="Live Intake" status="Recording">
            <div className="space-y-4">
                {/* Audio Waveform */}
                <div className="flex items-center gap-2 mb-4 px-1">
                    <div className="p-1.5 bg-green-500/10 rounded-full">
                        <Volume2 className="w-3.5 h-3.5 text-green-500" />
                    </div>
                    <div className="flex-1 flex items-center gap-0.5 h-4">
                        {[...Array(12)].map((_, i) => (
                            <motion.div
                                key={i}
                                animate={{ height: [4, 12, 4] }}
                                transition={{ duration: 1, repeat: Infinity, delay: i * 0.1, ease: "easeInOut" }}
                                className="w-1 bg-green-500/40 rounded-full"
                            />
                        ))}
                    </div>
                    <div className="text-[10px] font-mono text-muted-foreground">00:42</div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                    <Field label="Injury Site" value="Lower Back" delay={0.5} />
                    <Field label="Pain Level" value="5/10" delay={1.2} />
                    <div className="col-span-2">
                        <Field label="Clinical Note" value="Sharp pain when bending. Started after lifting boxes." delay={2.0} isLong />
                    </div>
                </div>
            </div>
        </LiveCard>
    )
}

function Field({ label, value, delay, isLong }: { label: string, value: string, delay: number, isLong?: boolean }) {
    return (
        <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay, duration: 0.4 }}
            className={`p-3 bg-muted/30 rounded-xl border border-border/40 ${isLong ? 'bg-primary/5 border-primary/10' : ''}`}
        >
            <div className="flex items-center justify-between mb-1">
                <div className="text-[9px] text-muted-foreground uppercase tracking-wider font-semibold">{label}</div>
                {isLong && <div className="text-[8px] bg-primary/20 text-primary px-1.5 rounded font-medium">Auto-Transcribed</div>}
            </div>
            <div className={`text-sm font-medium ${isLong ? 'text-primary/90 italic' : 'text-foreground'}`}>
                <Typewriter text={value} delay={delay + 0.3} />
            </div>
        </motion.div>
    )
}

function Typewriter({ text, delay }: { text: string, delay: number }) {
    const [displayed, setDisplayed] = useState("")

    useEffect(() => {
        const timeout = setTimeout(() => {
            let i = 0
            const interval = setInterval(() => {
                setDisplayed(text.substring(0, i + 1))
                i++
                if (i === text.length) clearInterval(interval)
            }, 30)
            return () => clearInterval(interval)
        }, delay * 1000)
        return () => clearTimeout(timeout)
    }, [text, delay])

    return <span>{displayed}{displayed.length < text.length && <span className="animate-pulse">|</span>}</span>
}

// Visual 4: Salon Deposit - Payment Secure
export function SalonVisual() {
    return (
        <LiveCard title="Revenue Guard" status="Enforcing">
            <div className="space-y-4">
                <div className="flex items-center justify-between pb-3 border-b border-dashed border-border/40">
                    <div>
                        <div className="text-xs font-semibold">Corrective Color</div>
                        <div className="text-[10px] text-muted-foreground">Standard Service</div>
                    </div>
                    <div className="text-xs font-mono bg-muted px-2 py-1 rounded text-foreground">3.5h</div>
                </div>

                <div className="space-y-3">
                    <div className="flex justify-between items-center text-[10px] text-muted-foreground uppercase tracking-wider px-1">
                        <span>Policy Check</span>
                        <span className="text-green-500 font-bold">PASSED</span>
                    </div>

                    <div className="relative overflow-hidden">
                        <div className="flex items-center justify-between bg-gradient-to-br from-emerald-500/10 to-transparent p-4 rounded-xl border border-emerald-500/20">
                            <div className="flex items-center gap-3">
                                <div className="p-2 bg-emerald-500/20 rounded-lg">
                                    <ShieldCheck className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
                                </div>
                                <div>
                                    <div className="text-[10px] text-emerald-600/80 uppercase tracking-widest font-semibold">Deposit</div>
                                    <div className="text-lg font-bold text-emerald-700 dark:text-emerald-300">$50.00</div>
                                </div>
                            </div>
                        </div>

                        {/* Stamp Animation */}
                        <motion.div
                            initial={{ scale: 2, opacity: 0, rotate: -20 }}
                            animate={{ scale: 1, opacity: 1, rotate: -12 }}
                            transition={{ delay: 1, type: "spring", bounce: 0.5 }}
                            className="absolute right-2 top-2 px-3 py-1 border-2 border-emerald-600 text-emerald-600 font-black text-xs rounded uppercase tracking-widest bg-background/80 backdrop-blur-sm shadow-lg"
                            style={{ textShadow: "0 0 1px rgba(0,0,0,0.1)" }}
                        >
                            Secured
                        </motion.div>
                    </div>
                </div>

                <div className="flex items-center justify-center gap-2 pt-2">
                    <Wifi className="w-3 h-3 text-muted-foreground" />
                    <div className="text-[10px] text-muted-foreground">Payment link sent via SMS</div>
                </div>
            </div>
        </LiveCard>
    )
}
