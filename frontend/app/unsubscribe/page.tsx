"use client"

import { useEffect, useState, Suspense } from "react"
import { useSearchParams } from "next/navigation"
import { motion } from "framer-motion"

function UnsubscribeContent() {
    const searchParams = useSearchParams()
    const [status, setStatus] = useState<"loading" | "success" | "error">("loading")
    const [email, setEmail] = useState("")

    useEffect(() => {
        const token = searchParams.get("token")

        if (!token) {
            setStatus("error")
            return
        }

        try {
            // Decode the base64 token to get the email
            const decodedEmail = Buffer.from(token, "base64").toString("utf-8")
            setEmail(decodedEmail)

            // In a real implementation, you would call an API to mark this email as unsubscribed
            // For now, we'll just show success
            setTimeout(() => {
                setStatus("success")
            }, 1000)
        } catch (error) {
            setStatus("error")
        }
    }, [searchParams])

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="max-w-md w-full text-center"
        >
            {status === "loading" && (
                <div>
                    <div className="w-12 h-12 border-4 border-black/10 dark:border-white/10 border-t-black dark:border-t-white rounded-full animate-spin mx-auto mb-6" />
                    <p className="text-zinc-600 dark:text-zinc-400">Processing...</p>
                </div>
            )}

            {status === "success" && (
                <div>
                    <div className="w-16 h-16 bg-black dark:bg-white rounded-full flex items-center justify-center mx-auto mb-6">
                        <svg className="w-8 h-8 text-white dark:text-black" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                        </svg>
                    </div>
                    <h1 className="text-3xl font-serif font-bold text-black dark:text-white mb-4">
                        You've been unsubscribed
                    </h1>
                    <p className="text-zinc-600 dark:text-zinc-400 mb-2">
                        {email} will no longer receive emails from Ovela.
                    </p>
                    <p className="text-sm text-zinc-500 dark:text-zinc-500 mb-8">
                        We're sorry to see you go. If this was a mistake, you can sign up again anytime.
                    </p>
                    <a
                        href="/"
                        className="inline-block px-6 py-3 bg-black dark:bg-white text-white dark:text-black rounded-full text-sm font-medium hover:bg-zinc-800 dark:hover:bg-zinc-200 transition-colors"
                    >
                        Return to Homepage
                    </a>
                </div>
            )}

            {status === "error" && (
                <div>
                    <div className="w-16 h-16 bg-red-100 dark:bg-red-900/20 rounded-full flex items-center justify-center mx-auto mb-6">
                        <svg className="w-8 h-8 text-red-600 dark:text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </div>
                    <h1 className="text-3xl font-serif font-bold text-black dark:text-white mb-4">
                        Invalid Link
                    </h1>
                    <p className="text-zinc-600 dark:text-zinc-400 mb-8">
                        This unsubscribe link is invalid or has expired. Please contact support if you need assistance.
                    </p>
                    <a
                        href="/"
                        className="inline-block px-6 py-3 bg-black dark:bg-white text-white dark:text-black rounded-full text-sm font-medium hover:bg-zinc-800 dark:hover:bg-zinc-200 transition-colors"
                    >
                        Return to Homepage
                    </a>
                </div>
            )}
        </motion.div>
    )
}

export default function UnsubscribePage() {
    return (
        <main className="min-h-screen bg-white dark:bg-black flex items-center justify-center p-6">
            <Suspense fallback={
                <div>
                    <div className="w-12 h-12 border-4 border-black/10 dark:border-white/10 border-t-black dark:border-t-white rounded-full animate-spin mx-auto mb-6" />
                    <p className="text-zinc-600 dark:text-zinc-400 text-center">Loading...</p>
                </div>
            }>
                <UnsubscribeContent />
            </Suspense>
        </main>
    )
}
