"use client"

import { motion, AnimatePresence, useMotionValue, useTransform } from "framer-motion"
import Link from "next/link"
import { useState, useEffect } from "react"
import LetterGlitch from "@/components/latter-glitch"

export default function NotFound() {
    const [phase, setPhase] = useState<"chaos" | "reveal">("chaos")
    const [showContent, setShowContent] = useState(false)
    const [animationProgress, setAnimationProgress] = useState(0)

    // Progress tracking for text visibility
    const chaosProgress = useMotionValue(0)
    const textOpacity = useTransform(chaosProgress, [0, 1], [0.15, 1])
    const subtextOpacity = useTransform(chaosProgress, [0, 0.5, 1], [0.1, 0.5, 0.9])

    useEffect(() => {
        // Animate the progress over the chaos phase duration
        const startTime = Date.now()
        const chaosDuration = 1800

        const progressInterval = setInterval(() => {
            const elapsed = Date.now() - startTime
            const progress = Math.min(elapsed / chaosDuration, 1)
            chaosProgress.set(progress)
            setAnimationProgress(progress)

            if (progress >= 1) {
                clearInterval(progressInterval)
            }
        }, 16)

        // Phase 1: Chaos (1.8s)
        const revealTimer = setTimeout(() => {
            setPhase("reveal")
        }, 1800)

        // Phase 2: Show content after transition
        const contentTimer = setTimeout(() => {
            setShowContent(true)
        }, 2200)

        return () => {
            clearInterval(progressInterval)
            clearTimeout(revealTimer)
            clearTimeout(contentTimer)
        }
    }, [chaosProgress])

    return (
        <div className="relative min-h-screen w-full overflow-hidden bg-black">
            {/* PHASE 1: CHAOS - Scary Glitch Background */}
            <AnimatePresence>
                {phase === "chaos" && (
                    <motion.div
                        className="absolute inset-0 z-10"
                        initial={{ opacity: 1 }}
                        exit={{ opacity: 0, scale: 1.1 }}
                        transition={{ duration: 0.6, ease: "easeOut" }}
                    >
                        {/* Letter Glitch Background - ERROR themed words */}
                        <div className="absolute inset-0 w-full h-full">
                            <LetterGlitch
                                glitchColors={['#ff0040', '#000000', '#1a0000']}
                                glitchSpeed={60}
                                centerVignette={false}
                                outerVignette={true}
                                smooth={false}
                                characters="ERROR404NOTFOUNDPAGENOTEXISTMISSING"
                            />
                        </div>

                        {/* Screen shake container */}
                        <motion.div
                            className="absolute inset-0 flex items-center justify-center"
                            animate={{
                                x: [0, -8, 8, -6, 6, -4, 4, 0],
                                y: [0, 4, -4, 6, -6, 2, -2, 0],
                            }}
                            transition={{
                                duration: 0.5,
                                repeat: 3,
                                ease: "easeInOut"
                            }}
                        >
                            {/* Scary Warning Text with Progressive Visibility */}
                            <motion.div
                                className="text-center"
                                animate={{
                                    scale: [1, 1.02, 0.98, 1.01, 1],
                                }}
                                transition={{
                                    duration: 0.3,
                                    repeat: Infinity,
                                }}
                            >
                                {/* Main 404 - Progressive opacity */}
                                <motion.h1
                                    className="text-[80px] sm:text-[120px] md:text-[160px] font-black tracking-tighter leading-none"
                                    style={{ opacity: textOpacity }}
                                >
                                    <span
                                        className="text-red-500"
                                        style={{
                                            textShadow: `0 0 ${30 + animationProgress * 40}px rgba(255,0,64,${0.4 + animationProgress * 0.5})`,
                                            filter: `drop-shadow(0 0 ${20 + animationProgress * 30}px rgba(255,0,64,0.8))`
                                        }}
                                    >
                                        404
                                    </span>
                                </motion.h1>

                                {/* Subtext with enhanced visibility and progressive reveal */}
                                <motion.p
                                    className="text-lg sm:text-xl md:text-2xl font-mono mt-4 tracking-widest font-bold"
                                    style={{
                                        opacity: subtextOpacity,
                                        color: '#ff6b6b',
                                        textShadow: '0 0 20px rgba(255,100,100,0.9), 0 0 40px rgba(255,0,64,0.6), 0 2px 4px rgba(0,0,0,0.8)'
                                    }}
                                    animate={{
                                        filter: ['brightness(1)', 'brightness(1.3)', 'brightness(1)']
                                    }}
                                    transition={{ duration: 0.2, repeat: Infinity }}
                                >
                                    PAGE_NOT_FOUND://ERROR
                                </motion.p>

                                {/* Additional warning text - appears with delay */}
                                <motion.div
                                    className="mt-6 space-y-2"
                                    initial={{ opacity: 0 }}
                                    animate={{ opacity: animationProgress > 0.3 ? (animationProgress - 0.3) / 0.7 : 0 }}
                                >
                                    <p
                                        className="text-sm sm:text-base font-mono tracking-wider"
                                        style={{
                                            color: '#ff4444',
                                            textShadow: '0 0 15px rgba(255,0,64,0.8), 0 0 30px rgba(255,0,64,0.4)'
                                        }}
                                    >
                                        ⚠ THIS PAGE DOES NOT EXIST ⚠
                                    </p>
                                    <motion.p
                                        className="text-xs sm:text-sm font-mono"
                                        style={{
                                            color: '#cc3333',
                                            textShadow: '0 0 10px rgba(255,0,64,0.6)'
                                        }}
                                        animate={{ opacity: [0.6, 1, 0.6] }}
                                        transition={{ duration: 0.3, repeat: Infinity }}
                                    >
                                        REDIRECTING...
                                    </motion.p>
                                </motion.div>
                            </motion.div>
                        </motion.div>

                        {/* Scanlines overlay */}
                        <div
                            className="absolute inset-0 pointer-events-none opacity-30"
                            style={{
                                background: 'repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.3) 2px, rgba(0,0,0,0.3) 4px)'
                            }}
                        />

                        {/* Red warning flash - enhanced */}
                        <motion.div
                            className="absolute inset-0 pointer-events-none"
                            style={{
                                background: 'radial-gradient(ellipse at center, rgba(255,0,64,0.25) 0%, rgba(0,0,0,0) 70%)'
                            }}
                            animate={{ opacity: [0, 0.4, 0, 0.3, 0] }}
                            transition={{ duration: 0.4, repeat: Infinity }}
                        />

                        {/* Edge glow effect */}
                        <div
                            className="absolute inset-0 pointer-events-none"
                            style={{
                                boxShadow: 'inset 0 0 100px rgba(255,0,64,0.3), inset 0 0 200px rgba(255,0,64,0.1)'
                            }}
                        />
                    </motion.div>
                )}
            </AnimatePresence>

            {/* PHASE 2: CALM REVEAL - Beautiful 404 with glitch background */}
            <motion.div
                className="absolute inset-0 z-0"
                initial={{ opacity: 0 }}
                animate={{ opacity: phase === "reveal" ? 1 : 0 }}
                transition={{ duration: 0.8 }}
            >
                {/* Letter Glitch Background - Error themed, full coverage */}
                <div className="absolute inset-0 w-full h-full">
                    <LetterGlitch
                        glitchColors={['#2a2a4e', '#d4bdb8', '#3d2a3d']}
                        glitchSpeed={100}
                        centerVignette={false}
                        outerVignette={true}
                        smooth={true}
                        characters="ERRORNOTFOUND404PAGEMISSINGLOSTBROKEN"
                    />
                </div>
            </motion.div>

            {/* Content Overlay - Appears in Phase 2 */}
            <AnimatePresence>
                {showContent && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ duration: 0.6 }}
                        className="relative z-20 flex flex-col items-center justify-center min-h-screen px-4"
                    >
                        {/* Dark backdrop to fade glitch text behind cube */}
                        <div
                            className="absolute inset-0 pointer-events-none"
                            style={{
                                background: 'radial-gradient(ellipse 60% 50% at 50% 50%, rgba(0,0,0,0.85) 0%, rgba(0,0,0,0.5) 40%, transparent 70%)',
                            }}
                        />

                        {/* Pure Image Approach - Photorealistic Ice Cube */}
                        <motion.div
                            className="relative z-10 flex items-center justify-center"
                            initial={{ opacity: 0, scale: 0.85, y: 20 }}
                            animate={{ opacity: 1, scale: 1, y: 0 }}
                            transition={{ delay: 0.2, duration: 1.2, ease: [0.16, 1, 0.3, 1] }}
                            style={{
                                width: '700px',
                                height: '700px',
                                maxWidth: '90vw',
                                maxHeight: '90vh',
                            }}
                        >
                            {/* Complete Ice Cube Image (with all text baked in) */}
                            <div
                                className="absolute inset-0"
                                style={{
                                    backgroundImage: 'url(/ice_cube.png)',
                                    backgroundSize: 'contain',
                                    backgroundPosition: 'center',
                                    backgroundRepeat: 'no-repeat',
                                    filter: 'drop-shadow(0 40px 100px rgba(0,0,0,0.7)) drop-shadow(0 20px 50px rgba(0,0,0,0.5))',
                                }}
                            />

                            {/* Invisible Clickable Button Overlay - Positioned exactly on image button */}
                            <motion.div
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                transition={{ delay: 1, duration: 0.5 }}
                                className="absolute bottom-[37%]  left-[46%] md:bottom-[26%] md:left-[47%]"
                                style={{
                                    transform: 'translateX(-50%)',
                                }}
                            >
                                <Link href="/">
                                    <motion.button
                                        whileHover={{
                                            scale: 1.08,
                                            filter: 'brightness(1.2)',
                                        }}
                                        whileTap={{ scale: 0.95 }}
                                        className="px-15 py-4 md:px-24 md:py-7 rounded-full cursor-pointer md:-ml-5"
                                        style={{
                                            background: 'transparent',
                                            border: 'none',
                                            opacity: 0,
                                        }}
                                        aria-label="Take me home"
                                    >
                                        {/* Empty - button is invisible */}
                                    </motion.button>
                                </Link>
                            </motion.div>

                            {/* Subtle ambient glow */}
                            <div
                                className="absolute inset-0 pointer-events-none"
                                style={{
                                    background: 'radial-gradient(ellipse 60% 50% at 50% 45%, rgba(200, 230, 255, 0.12) 0%, transparent 65%)',
                                    filter: 'blur(50px)',
                                    opacity: 0.5,
                                }}
                            />
                        </motion.div>

                        {/* Brand footer */}
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            transition={{ delay: 1, duration: 0.5 }}
                            className="absolute bottom-8 left-1/2 -translate-x-1/2 z-10"
                        >
                            <div
                                className="flex items-center gap-2 text-sm"
                                style={{
                                    color: 'rgba(255,255,255,0.5)',
                                }}
                            >
                                <motion.div
                                    className="w-2 h-2 rounded-full bg-[#d4bdb8]"
                                    animate={{ opacity: [0.5, 1, 0.5] }}
                                    transition={{ duration: 2, repeat: Infinity }}
                                    style={{
                                        boxShadow: '0 0 10px rgba(212,189,184,0.5)'
                                    }}
                                />
                                <span className="tracking-wider font-medium">Ovela AI</span>
                            </div>
                        </motion.div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Ambient floating particles (both phases) */}
            <div className="absolute inset-0 z-5 pointer-events-none overflow-hidden">
                {[...Array(10)].map((_, i) => (
                    <motion.div
                        key={i}
                        className="absolute w-1 h-1 rounded-full"
                        style={{
                            backgroundColor: phase === "chaos" ? "rgba(255,0,64,0.4)" : "rgba(212,189,184,0.3)",
                            left: `${5 + i * 10}%`,
                        }}
                        initial={{ y: "100vh", opacity: 0 }}
                        animate={{
                            y: "-10vh",
                            opacity: [0, 1, 0],
                            x: Math.sin(i) * 30
                        }}
                        transition={{
                            duration: 6 + i * 0.5,
                            repeat: Infinity,
                            delay: i * 0.6,
                            ease: "linear",
                        }}
                    />
                ))}
            </div>
        </div>
    )
}
