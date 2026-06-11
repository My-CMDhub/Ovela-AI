"use client"

import { useEffect, useState, useRef } from "react"
import { motion } from "framer-motion"

interface DecodingTextProps {
    text: string
    className?: string
    animateRequest?: any // Prop to trigger re-animation if needed, usually changing text is enough
}

const CHARACTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890!@#$%^&*()_+"

export function DecodingText({ text, className }: DecodingTextProps) {
    const [displayText, setDisplayText] = useState(text)
    const [isScrambling, setIsScrambling] = useState(false)
    const iterations = useRef(0)

    useEffect(() => {
        // Trigger animation when text changes
        setIsScrambling(true)
        iterations.current = 0

        const interval = setInterval(() => {
            setDisplayText(current => {
                return text
                    .split("")
                    .map((char, index) => {
                        if (index < iterations.current) {
                            return text[index]
                        }
                        return CHARACTERS[Math.floor(Math.random() * CHARACTERS.length)]
                    })
                    .join("")
            })

            if (iterations.current >= text.length) {
                clearInterval(interval)
                setIsScrambling(false)
            }

            iterations.current += 1 / 2 // Speed of decoding (lower denominator = faster)
        }, 30)

        return () => clearInterval(interval)
    }, [text])

    return (
        <span className={className}>
            {displayText}
        </span>
    )
}
