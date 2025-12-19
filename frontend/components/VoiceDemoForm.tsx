"use client"

import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Phone, Check, Loader2, AlertCircle, ArrowRight } from "lucide-react"
import { cn } from "@/lib/utils"

interface VoiceDemoFormProps {
    className?: string
}

export function VoiceDemoForm({ className }: VoiceDemoFormProps) {
    const [step, setStep] = useState<"form" | "calling" | "ended">("form")
    const [isLoading, setIsLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const [formData, setFormData] = useState({
        name: "",
        businessName: "",
        phone: "",
        consent: false
    })

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        setError(null)

        if (!formData.consent) {
            setError("Please agree to the consent term to proceed.")
            return
        }

        // Basic validation for +61 or 04 numbers
        const phoneRegex = /^(\+61|0)4\d{8}$/
        const cleanedPhone = formData.phone.replace(/\s/g, "")
        if (!phoneRegex.test(cleanedPhone)) {
            setError("Please enter a valid Australian mobile number (e.g., 0412 345 678).")
            return
        }

        setIsLoading(true)

        try {
            // Convert 04 to +61 format for backend
            const phoneForBackend = cleanedPhone.startsWith("0")
                ? `+61${cleanedPhone.substring(1)}`
                : cleanedPhone

            const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/voice/demo-request`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    name: formData.name,
                    business_name: formData.businessName,
                    phone: phoneForBackend,
                    consent: formData.consent
                })
            })

            if (!response.ok) {
                const errorData = await response.json()
                throw new Error(errorData.detail || "Failed to initiate call")
            }

            const data = await response.json()
            console.log("Call initiated:", data)

            setStep("calling")
        } catch (err: unknown) {
            console.error("Demo request error:", err)
            const message = err instanceof Error ? err.message : "Something went wrong. Please try again."
            setError(message)
        } finally {
            setIsLoading(false)
        }
    }

    const handleReset = () => {
        setStep("form")
        setError(null)
        setFormData({ name: "", businessName: "", phone: "", consent: false })
    }

    return (
        <div className={cn("w-full max-w-md mx-auto", className)}>
            <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="relative overflow-hidden rounded-2xl border border-gray-200 dark:border-white/10 bg-white/80 dark:bg-black/40 backdrop-blur-xl shadow-2xl"
            >
                {/* Ambient Glow */}
                <div className="absolute top-0 right-0 -mr-20 -mt-20 w-60 h-60 bg-purple-500/20 rounded-full blur-3xl pointer-events-none" />
                <div className="absolute bottom-0 left-0 -ml-20 -mb-20 w-60 h-60 bg-blue-500/20 rounded-full blur-3xl pointer-events-none" />

                <div className="relative p-6 sm:p-8">

                    {/* Header */}
                    <div className="mb-6 space-y-2 text-center">
                        <h3 className="text-2xl font-bold tracking-tight text-gray-900 dark:text-white">
                            Try Ovela Now
                        </h3>
                        <p className="text-sm text-gray-600 dark:text-gray-400">
                            Enter your number and we'll call you instantly.
                            <br />
                            <span className="text-xs text-gray-500 dark:text-white/50">(Australian numbers only)</span>
                        </p>
                    </div>

                    <AnimatePresence mode="wait">
                        {step === "form" && (
                            <motion.form
                                key="form"
                                initial={{ opacity: 0, x: -20 }}
                                animate={{ opacity: 1, x: 0 }}
                                exit={{ opacity: 0, x: 20 }}
                                onSubmit={handleSubmit}
                                className="space-y-4"
                            >
                                <div>
                                    <input
                                        type="text"
                                        placeholder="Your Name"
                                        required
                                        value={formData.name}
                                        onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                                        className="w-full px-4 py-3 bg-gray-50 dark:bg-white/5 border border-gray-200 dark:border-white/10 rounded-lg text-gray-900 dark:text-white placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500/50 transition-all font-light"
                                    />
                                </div>
                                <div>
                                    <input
                                        type="text"
                                        placeholder="Business Name"
                                        required
                                        value={formData.businessName}
                                        onChange={(e) => setFormData(prev => ({ ...prev, businessName: e.target.value }))}
                                        className="w-full px-4 py-3 bg-gray-50 dark:bg-white/5 border border-gray-200 dark:border-white/10 rounded-lg text-gray-900 dark:text-white placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500/50 transition-all font-light"
                                    />
                                </div>
                                <div>
                                    <input
                                        type="tel"
                                        placeholder="Mobile Number (04...)"
                                        required
                                        value={formData.phone}
                                        onChange={(e) => setFormData(prev => ({ ...prev, phone: e.target.value }))}
                                        className="w-full px-4 py-3 bg-gray-50 dark:bg-white/5 border border-gray-200 dark:border-white/10 rounded-lg text-gray-900 dark:text-white placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500/50 transition-all font-light"
                                    />
                                </div>

                                {/* Consent */}
                                <div className="flex items-start gap-3 pt-2">
                                    <div className="flex h-5 items-center">
                                        <input
                                            id="consent"
                                            type="checkbox"
                                            checked={formData.consent}
                                            onChange={(e) => setFormData(prev => ({ ...prev, consent: e.target.checked }))}
                                            className="h-4 w-4 rounded border-gray-300 dark:border-white/10 bg-gray-50 dark:bg-white/5 text-purple-600 focus:ring-purple-500/50"
                                        />
                                    </div>
                                    <label htmlFor="consent" className="text-xs text-gray-600 dark:text-gray-400 text-left leading-tight">
                                        I agree to receive a demo call from Ovela AI. I understand this call is automated and may be recorded for quality purposes.
                                    </label>
                                </div>

                                {/* Error Message */}
                                <AnimatePresence>
                                    {error && (
                                        <motion.div
                                            initial={{ opacity: 0, height: 0 }}
                                            animate={{ opacity: 1, height: "auto" }}
                                            exit={{ opacity: 0, height: 0 }}
                                            className="text-red-600 dark:text-red-400 text-xs flex items-center gap-2 bg-red-50 dark:bg-red-500/10 p-2 rounded"
                                        >
                                            <AlertCircle className="w-4 h-4" />
                                            {error}
                                        </motion.div>
                                    )}
                                </AnimatePresence>

                                {/* Submit Button */}
                                <button
                                    type="submit"
                                    disabled={isLoading}
                                    className="group w-full relative flex items-center justify-center gap-2 py-3 px-4 bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 text-white font-medium rounded-lg transition-all duration-200 shadow-lg shadow-purple-500/20 hover:shadow-purple-500/40 disabled:opacity-70 disabled:cursor-not-allowed mt-2"
                                >
                                    {isLoading ? (
                                        <Loader2 className="w-5 h-5 animate-spin" />
                                    ) : (
                                        <>
                                            Call Me Now
                                            <Phone className="w-4 h-4 fill-current" />
                                        </>
                                    )}

                                    {/* Sheen Effect */}
                                    <div className="absolute inset-0 overflow-hidden rounded-lg pointer-events-none">
                                        <div className="absolute -inset-full top-0 block h-full w-1/2 -skew-x-12 bg-gradient-to-r from-transparent to-white opacity-20 group-hover:animate-shine" />
                                    </div>
                                </button>
                            </motion.form>
                        )}

                        {step === "calling" && (
                            <motion.div
                                key="calling"
                                initial={{ opacity: 0, scale: 0.9 }}
                                animate={{ opacity: 1, scale: 1 }}
                                className="text-center py-8 space-y-6"
                            >
                                {/* Simple animated phone icon */}
                                <div className="relative w-20 h-20 mx-auto">
                                    <div className="absolute inset-0 bg-purple-500/20 rounded-full animate-ping" />
                                    <div className="relative bg-gradient-to-br from-purple-600 to-blue-600 rounded-full w-20 h-20 flex items-center justify-center shadow-xl shadow-purple-500/30">
                                        <Phone className="w-8 h-8 text-white animate-pulse" />
                                    </div>
                                </div>

                                {/* Simplified status message */}
                                <div className="space-y-3">
                                    <h4 className="text-xl font-semibold text-gray-900 dark:text-white">Call Initiated</h4>
                                    <p className="text-sm text-gray-600 dark:text-gray-400">
                                        Your phone should ring shortly.
                                    </p>
                                    <p className="text-xs text-gray-500 dark:text-white/40">
                                        If you don't receive a call within 30 seconds, please try again.
                                    </p>
                                </div>

                                {/* Try Again Button */}
                                <button
                                    onClick={handleReset}
                                    className="mt-4 inline-flex items-center gap-2 text-sm text-purple-600 dark:text-purple-400 hover:text-purple-700 dark:hover:text-purple-300 transition-colors"
                                >
                                    Start Over <ArrowRight className="w-4 h-4" />
                                </button>
                            </motion.div>
                        )}

                        {step === "ended" && (
                            <motion.div
                                key="ended"
                                initial={{ opacity: 0, scale: 0.9 }}
                                animate={{ opacity: 1, scale: 1 }}
                                className="text-center py-8 space-y-4"
                            >
                                <div className="relative w-20 h-20 mx-auto">
                                    <div className="relative bg-gradient-to-br from-green-500 to-teal-600 rounded-full w-20 h-20 flex items-center justify-center shadow-xl shadow-green-500/30">
                                        <Check className="w-8 h-8 text-white" />
                                    </div>
                                </div>
                                <div>
                                    <h4 className="text-xl font-semibold text-gray-900 dark:text-white">Thanks for trying Ovela!</h4>
                                    <p className="text-sm text-gray-600 dark:text-gray-400 mt-2">
                                        We hope you enjoyed the demo.
                                    </p>
                                    <button
                                        onClick={handleReset}
                                        className="mt-4 inline-flex items-center gap-2 text-sm text-purple-600 dark:text-purple-400 hover:text-purple-700 dark:hover:text-purple-300 transition-colors"
                                    >
                                        Try again <ArrowRight className="w-4 h-4" />
                                    </button>
                                </div>
                            </motion.div>
                        )}
                    </AnimatePresence>

                </div>
            </motion.div>
        </div>
    )
}
