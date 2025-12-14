"use client"

import { useEffect, useState } from "react"
import { motion } from "framer-motion"

export function DarkModeToggle() {
    const [isDark, setIsDark] = useState(false)

    // Check system/saved preference on mount
    useEffect(() => {
        const savedTheme = localStorage.getItem("theme")
        const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches

        if (savedTheme === "dark" || (!savedTheme && prefersDark)) {
            setIsDark(true)
            document.documentElement.classList.add("dark")
        }
    }, [])

    const toggleDarkMode = () => {
        setIsDark(!isDark)

        if (!isDark) {
            document.documentElement.classList.add("dark")
            localStorage.setItem("theme", "dark")
        } else {
            document.documentElement.classList.remove("dark")
            localStorage.setItem("theme", "light")
        }
    }

    return (
        <motion.button
            onClick={toggleDarkMode}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            className="p-2 rounded-lg bg-muted/50 hover:bg-muted transition-colors duration-200"
            aria-label="Toggle dark mode"
        >
            <motion.div
                initial={false}
                animate={{ rotate: isDark ? 270 : 0 }}
                transition={{ duration: 0.3, ease: "easeInOut" }}
            >
                {isDark ? (
                    // Moon icon
                    <svg
                        className="w-5 h-5 text-foreground"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                        strokeWidth="2"
                    >
                        <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"
                        />
                    </svg>
                ) : (
                    // Sun icon
                    <svg
                        className="w-5 h-5 text-foreground"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                        strokeWidth="2"
                    >
                        <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"
                        />
                    </svg>
                )}
            </motion.div>
        </motion.button>
    )
}
