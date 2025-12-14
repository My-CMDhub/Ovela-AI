"use client"

import { cn } from "@/lib/utils"
import { motion } from "framer-motion"
import React from "react"

export const WavyBackground = ({
    className,
    containerClassName,
    colors,
    waveWidth,
    backgroundFill,
    blur = 10,
    speed = "fast",
    waveOpacity = 0.5,
    ...props
}: {
    className?: string
    containerClassName?: string
    colors?: string[]
    waveWidth?: number
    backgroundFill?: string
    blur?: number
    speed?: "slow" | "fast"
    waveOpacity?: number
    [key: string]: any
}) => {
    const noise =
        "url(\"data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)' opacity='0.05'/%3E%3C/svg%3E\")"

    const _colors = colors ?? [
        "#38bdf8",
        "#818cf8",
        "#c084fc",
        "#e879f9",
        "#22d3ee",
    ]

    return (
        <div
            className={cn(
                "h-full w-full flex flex-col items-center justify-center overflow-hidden relative",
                containerClassName
            )}
        >
            <div
                className="absolute inset-0 z-0 opacity-50"
                style={{
                    backgroundImage: noise,
                }}
            />
            <div className={cn("relative z-10", className)} {...props}>
                {props.children}
            </div>
            <div className="absolute inset-0 z-0">
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ duration: 2 }}
                    className="h-full w-full relative"
                >
                    {_colors.map((color, i) => (
                        <motion.div
                            key={i}
                            className="absolute rounded-full mix-blend-screen filter blur-[100px] opacity-70"
                            style={{
                                background: color,
                                width: "40vw",
                                height: "40vw",
                                top: "50%",
                                left: "50%",
                                transform: "translate(-50%, -50%)",
                            }}
                            animate={{
                                x: [
                                    Math.random() * 400 - 200,
                                    Math.random() * 400 - 200,
                                    Math.random() * 400 - 200,
                                ],
                                y: [
                                    Math.random() * 400 - 200,
                                    Math.random() * 400 - 200,
                                    Math.random() * 400 - 200,
                                ],
                                scale: [1, 1.2, 1],
                            }}
                            transition={{
                                duration: Math.random() * 10 + 10,
                                repeat: Infinity,
                                repeatType: "reverse",
                                ease: "easeInOut",
                            }}
                        />
                    ))}
                </motion.div>
            </div>
        </div>
    )
}
