"use client"

import { motion } from "framer-motion"

const ecosystems = [
    { name: "ServiceM8", color: "#66CC00" },
    { name: "RMS Cloud", color: "#005EB8" },
    { name: "Tradify", color: "#FFB81C" },
    { name: "Cliniko", color: "#2F2F2F" },
    { name: "Xero", color: "#13B5EA" },
    { name: "Fergus", color: "#FF6B00" },
    { name: "Cloudbeds", color: "#00B4D8" },
    { name: "Halaxy", color: "#4A90E2" },
    { name: "Timely", color: "#8E44AD" },
]

export function EcosystemLoop() {
    return (
        <div className="w-full py-12 border-y border-border/40 bg-muted/20 overflow-hidden relative flex items-center">
            {/* Gradient Fade Masks */}
            <div className="absolute left-0 top-0 bottom-0 w-24 bg-gradient-to-r from-background to-transparent z-10" />
            <div className="absolute right-0 top-0 bottom-0 w-24 bg-gradient-to-l from-background to-transparent z-10" />

            {/* Label */}
            <div className="hidden md:flex items-center gap-2 px-8 shrink-0 z-20 border-r border-border/50 mr-8 bg-background/50 backdrop-blur-sm py-2 rounded-r-full">
                <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                <span className="text-xs font-bold text-muted-foreground uppercase tracking-widest whitespace-nowrap">
                    Works Native With
                </span>
            </div>

            {/* Scrolling Track */}
            <div className="flex overflow-hidden flex-1 mask-image relative">
                <motion.div
                    className="flex gap-16 min-w-max"
                    animate={{ x: ["0%", "-50%"] }}
                    transition={{
                        duration: 30,
                        ease: "linear",
                        repeat: Infinity,
                    }}
                >
                    {/* Triplicate the list to ensure smooth seamless loop */}
                    {[...ecosystems, ...ecosystems, ...ecosystems, ...ecosystems].map((system, i) => (
                        <div
                            key={i}
                            className="flex items-center gap-2 shrink-0 grayscale hover:grayscale-0 transition-all duration-500 opacity-50 hover:opacity-100 cursor-default"
                        >
                            <span className="text-xl font-bold tracking-tight text-foreground" style={{ fontFamily: 'system-ui' }}>
                                {system.name}
                            </span>
                        </div>
                    ))}
                </motion.div>
            </div>
        </div>
    )
}
