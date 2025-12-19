"use client"

import { motion, AnimatePresence } from "framer-motion"
import { useEffect, useState } from "react"

export function Preloader({ onComplete }: { onComplete: () => void }) {
    const [index, setIndex] = useState(0)
    const [shouldShow, setShouldShow] = useState(false)
    const words = ["Beauty", "Intelligence", "Ovela"]
    const colors = [
        "#F4EFE9", // Soft Beige (Beauty)
        "#E9D5FF", // Soft Lavender (Intelligence)
        "#1A1A1A"  // Dark Brand Color (Ovela)
    ]

    // Text colors corresponding to backgrounds to ensure contrast
    const textColors = [
        "#1A1A1A", // Dark text on Beige
        "#1A1A1A", // Dark text on Lavender
        "#FFFFFF"  // White text on Dark
    ]

    // Check if this is the first visit
    useEffect(() => {
        const hasVisited = localStorage.getItem('ovela_visited')
        if (!hasVisited) {
            setShouldShow(true)
            localStorage.setItem('ovela_visited', 'true')
        } else {
            // Skip preloader for returning visitors
            onComplete()
        }
    }, [onComplete])

    useEffect(() => {
        if (!shouldShow) return

        if (index === words.length) {
            // Trigger completion after the last word has been shown
            const timer = setTimeout(() => {
                onComplete()
            }, 800)
            return () => clearTimeout(timer)
        }

        const timer = setTimeout(() => {
            setIndex((prev) => prev + 1)
        }, 600) // Faster animation for better LCP

        return () => clearTimeout(timer)
    }, [index, words.length, onComplete, shouldShow])

    // Don't render if shouldn't show
    if (!shouldShow) return null

    return (
        <motion.div
            className="fixed inset-0 z-[100] flex items-center justify-center overflow-hidden"
            initial={{ y: 0 }}
            exit={{
                y: "-100%",
                transition: { duration: 1, ease: [0.76, 0, 0.24, 1] } // Custom bezier for premium "curtain" feel
            }}
        >
            {/* Background Color Transition */}
            <motion.div
                className="absolute inset-0 w-full h-full"
                animate={{ backgroundColor: index < colors.length ? colors[index] : colors[colors.length - 1] }}
                transition={{ duration: 0.8, ease: "easeInOut" }}
            />

            <AnimatePresence mode="wait">
                {index < words.length && (
                    <motion.div
                        key={index}
                        initial={{ opacity: 0, y: 20, filter: "blur(10px)" }}
                        animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
                        exit={{ opacity: 0, y: -20, filter: "blur(10px)" }}
                        transition={{ duration: 0.6, ease: "easeOut" }}
                        className="absolute z-10"
                    >
                        <h1
                            className="text-6xl md:text-9xl font-serif tracking-tighter"
                            style={{ color: index < textColors.length ? textColors[index] : textColors[textColors.length - 1] }}
                        >
                            {words[index]}
                            <span className="text-accent">.</span>
                        </h1>
                    </motion.div>
                )}
            </AnimatePresence>
        </motion.div>
    )
}
