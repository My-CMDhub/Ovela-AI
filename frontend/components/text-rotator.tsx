"use client"

import { useEffect, useState } from "react"
import { motion, AnimatePresence } from "framer-motion"

interface TextRotatorProps {
    texts: string[]
    className?: string
}

export function TextRotator({ texts, className = "" }: TextRotatorProps) {
    const [index, setIndex] = useState(0)

    useEffect(() => {
        const interval = setInterval(() => {
            setIndex((prev) => (prev + 1) % texts.length)
        }, 2000) // Change every 2 seconds
        return () => clearInterval(interval)
    }, [texts.length])

    return (
        <div className={`relative block overflow-hidden w-full h-[1.4em] text-center ${className}`}>
            <AnimatePresence mode="popLayout" initial={false}>
                <motion.span
                    key={index}
                    initial={{ y: "110%", opacity: 0, filter: "blur(8px)" }}
                    animate={{ y: "0%", opacity: 1, filter: "blur(0px)" }}
                    exit={{ y: "-110%", opacity: 0, filter: "blur(8px)" }}
                    transition={{
                        y: { type: "spring", stiffness: 70, damping: 15 },
                        opacity: { duration: 0.4 },
                        filter: { duration: 0.4 }
                    }}
                    className="absolute inset-0 block w-full text-accent bg-clip-text text-transparent bg-gradient-to-r from-accent to-accent/80"
                >
                    {texts[index]}
                </motion.span>
            </AnimatePresence>
        </div>
    )
}
