"use client"

import { useState } from "react"
import { motion, useMotionValue, useTransform, animate } from "framer-motion"

interface OvelaLogoProps {
    size?: "sm" | "md" | "lg"
    className?: string
}

export function OvelaLogo({ size = "md", className = "" }: OvelaLogoProps) {
    const [isHovered, setIsHovered] = useState(false)

    // Size configurations
    const sizeConfig = {
        sm: { oSize: 28, fontSize: "1.2rem", letterSpacing: 2, strokeWidth: 2.5, slideDistance: 24 },
        md: { oSize: 36, fontSize: "1.5rem", letterSpacing: 3, strokeWidth: 3, slideDistance: 31 },
        lg: { oSize: 56, fontSize: "3.2rem", letterSpacing: 4, strokeWidth: 5, slideDistance: 47.5 },
    }

    const config = sizeConfig[size]

    // Main timeline progress - using motion value for separate forward/reverse control
    const progress = useMotionValue(0)

    // Separate spring for suction waves
    const [showSuctionWaves, setShowSuctionWaves] = useState(false)

    const handleHover = (hovered: boolean) => {
        setIsHovered(hovered)

        if (hovered) {
            // Fast forward animation with spring physics
            animate(progress, 1, {
                type: "spring",
                stiffness: 35,
                damping: 20,
                mass: 1.2,
            })
            setTimeout(() => setShowSuctionWaves(true), 100)
            setTimeout(() => setShowSuctionWaves(false), 1600)
        } else {
            // Slow reverse animation with ease-out
            animate(progress, 0, {
                type: "tween",
                duration: 2.8,
                ease: "easeOut",
            })
            setShowSuctionWaves(false)
        }
    }

    // Mouth animation - pause at 92-95% to digest, then close 95-99%
    const mouthAngle = useTransform(progress, [0, 0.12, 0.95, 0.99], [0, 38, 38, 0])

    // O slides when mouth starts closing (at 95%)
    const oTranslateX = useTransform(progress, [0.95, 1], [0, config.slideDistance])

    // Glow pulse at the very end
    const glowOpacity = useTransform(progress, [0.92, 1], [0, 0.8])
    const glowScale = useTransform(progress, [0.92, 1], [0.95, 1.05])

    // Brand accent opacity (always visible on O, intensifies on complete)
    const accentOpacity = useTransform(progress, [0, 0.5, 1], [0.4, 0.6, 1])

    // Letter animations - start after 2s of wave visibility
    const v_progress = useTransform(progress, [0.65, 0.85], [0, 1])
    const v_x = useTransform(v_progress, [0, 0.3, 0.5, 0.75, 0.92, 1], [0, 0, -8, -18, -28, -35])
    const v_scale = useTransform(v_progress, [0, 0.3, 0.6, 0.85, 1], [1, 0.85, 0.55, 0.25, 0])
    const v_opacity = useTransform(v_progress, [0, 0.85, 1], [1, 1, 0])

    const e_progress = useTransform(progress, [0.68, 0.87], [0, 1])
    const e_x = useTransform(e_progress, [0, 0.3, 0.5, 0.75, 0.92, 1], [0, 0, -10, -22, -35, -45])
    const e_scale = useTransform(e_progress, [0, 0.3, 0.6, 0.85, 1], [1, 0.85, 0.55, 0.25, 0])
    const e_opacity = useTransform(e_progress, [0, 0.85, 1], [1, 1, 0])

    const l_progress = useTransform(progress, [0.71, 0.89], [0, 1])
    const l_x = useTransform(l_progress, [0, 0.3, 0.5, 0.75, 0.92, 1], [0, 0, -12, -26, -40, -52])
    const l_scale = useTransform(l_progress, [0, 0.3, 0.6, 0.85, 1], [1, 0.85, 0.55, 0.25, 0])
    const l_opacity = useTransform(l_progress, [0, 0.85, 1], [1, 1, 0])

    const a_progress = useTransform(progress, [0.74, 0.92], [0, 1])
    const a_x = useTransform(a_progress, [0, 0.3, 0.5, 0.75, 0.92, 1], [0, 0, -14, -30, -48, -60])
    const a_scale = useTransform(a_progress, [0, 0.3, 0.6, 0.85, 1], [1, 0.85, 0.55, 0.25, 0])
    const a_opacity = useTransform(a_progress, [0, 0.85, 1], [1, 1, 0])

    const center = config.oSize / 2
    const radius = config.oSize / 2 - config.strokeWidth

    // Brand pink/purple color
    const brandColor = "rgb(216, 180, 254)"
    const brandColorDim = "rgba(216, 180, 254, 0.6)"
    const brandColorFaint = "rgba(216, 180, 254, 0.3)"

    return (
        <div
            className={`relative flex items-center cursor-pointer select-none ${className}`}
            onMouseEnter={() => handleHover(true)}
            onMouseLeave={() => handleHover(false)}
        >
            <div className="relative flex items-center">
                {/* The signature "O" with Pac-Man mouth - uses overflow-visible for rings */}
                <motion.div className="relative z-30 flex-shrink-0" style={{ x: oTranslateX }}>
                    <svg
                        width={config.oSize}
                        height={config.oSize}
                        viewBox={`0 0 ${config.oSize} ${config.oSize}`}
                        className="overflow-visible"
                        style={{ overflow: "visible" }}
                    >
                        <defs>
                            {/* Brand gradient for the O */}
                            <linearGradient id="oGradientBrand" x1="0%" y1="0%" x2="100%" y2="100%">
                                <stop offset="0%" stopColor="currentColor" />
                                <stop offset="50%" stopColor="currentColor" />
                                <stop offset="100%" stopColor={brandColor} />
                            </linearGradient>

                            {/* Glow filter for the ring */}
                            <filter id="oGlowBrand" x="-100%" y="-100%" width="300%" height="300%">
                                <feGaussianBlur stdDeviation="4" result="blur" />
                                <feMerge>
                                    <feMergeNode in="blur" />
                                    <feMergeNode in="SourceGraphic" />
                                </feMerge>
                            </filter>
                        </defs>

                        {/* Outer glow ring - Brand pink/purple */}
                        <motion.circle
                            cx={center}
                            cy={center}
                            r={radius + 5}
                            fill="none"
                            stroke={brandColor}
                            strokeWidth="2"
                            style={{
                                opacity: glowOpacity,
                                scale: glowScale,
                                transformOrigin: "center center",
                            }}
                            filter="url(#oGlowBrand)"
                        />

                        {/* Main O ring - bold & heavy with thick stroke */}
                        <circle
                            cx={center}
                            cy={center}
                            r={radius}
                            fill="none"
                            stroke="url(#oGradientBrand)"
                            strokeWidth={config.strokeWidth * 2.5}
                        />

                        {/* Inner ring for double-ring depth effect */}
                        <circle
                            cx={center}
                            cy={center}
                            r={radius - config.strokeWidth * 2}
                            fill="none"
                            stroke="url(#oGradientBrand)"
                            strokeWidth={config.strokeWidth * 0.8}
                            opacity={0.4}
                        />

                        {/* Subtle inner accent dots - voice hint */}
                        <motion.g style={{ opacity: accentOpacity }}>
                            <circle
                                cx={center + radius * 0.65}
                                cy={center - radius * 0.35}
                                r={1.5}
                                fill={brandColor}
                                opacity={0.8}
                            />
                            <circle
                                cx={center + radius * 0.65}
                                cy={center + radius * 0.35}
                                r={1}
                                fill={brandColor}
                                opacity={0.5}
                            />
                        </motion.g>

                        {/* Mouth cutout - matches background */}
                        <motion.path
                            className="fill-background"
                            style={{
                                d: useTransform(mouthAngle, (angle) => {
                                    if (angle <= 0.5) return `M ${center} ${center} L ${center} ${center} L ${center} ${center} Z`
                                    const rad = (angle * Math.PI) / 180
                                    const cutRadius = radius + config.strokeWidth + 2
                                    const x1 = center + cutRadius * Math.cos(-rad)
                                    const y1 = center + cutRadius * Math.sin(-rad)
                                    const x2 = center + cutRadius * Math.cos(rad)
                                    const y2 = center + cutRadius * Math.sin(rad)
                                    return `M ${center} ${center} L ${x1} ${y1} A ${cutRadius} ${cutRadius} 0 0 1 ${x2} ${y2} Z`
                                }),
                            }}
                        />
                    </svg>

                    {/* Magnetic suction wave lines */}
                    <motion.div
                        className="absolute inset-0 pointer-events-none"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: showSuctionWaves ? 1 : 0 }}
                        transition={{ duration: 0.2 }}
                    >
                        <svg
                            width={config.oSize}
                            height={config.oSize}
                            viewBox={`0 0 ${config.oSize} ${config.oSize}`}
                            className="overflow-visible"
                        >
                            <motion.path
                                d={`M ${config.oSize + 4} ${center - 8} Q ${config.oSize + 14} ${center} ${config.oSize + 4} ${center + 8}`}
                                fill="none"
                                stroke={brandColorDim}
                                strokeWidth="1.5"
                                strokeLinecap="round"
                                initial={{ pathLength: 0, x: 0 }}
                                animate={
                                    showSuctionWaves
                                        ? { pathLength: [0, 1, 1], x: [20, 0, -10], opacity: [0, 0.7, 0] }
                                        : { pathLength: 0, opacity: 0 }
                                }
                                transition={{ duration: 0.6, repeat: showSuctionWaves ? Infinity : 0, repeatDelay: 0.1 }}
                            />
                            <motion.path
                                d={`M ${config.oSize + 19} ${center - 10} Q ${config.oSize + 32} ${center} ${config.oSize + 19} ${center + 10}`}
                                fill="none"
                                stroke={brandColorFaint}
                                strokeWidth="1.5"
                                strokeLinecap="round"
                                initial={{ pathLength: 0, x: 0 }}
                                animate={
                                    showSuctionWaves
                                        ? { pathLength: [0, 1, 1], x: [25, 0, -15], opacity: [0, 0.5, 0] }
                                        : { pathLength: 0, opacity: 0 }
                                }
                                transition={{ duration: 0.7, delay: 0.1, repeat: showSuctionWaves ? Infinity : 0, repeatDelay: 0.1 }}
                            />
                        </svg>
                    </motion.div>
                </motion.div>

                {/* Mask that moves with O to hide consumed letters */}
                <motion.div
                    className="absolute left-0 top-0 bottom-0 z-20 pointer-events-none bg-background"
                    style={{
                        x: oTranslateX,
                        width: `${config.oSize}px`,
                    }}
                />

                {/* Letters container - above O ring so they don't get clipped */}
                <div className="relative z-40 flex items-center" style={{ marginLeft: `${config.letterSpacing}px` }}>
                    <motion.span
                        className="font-semibold text-foreground inline-block will-change-transform"
                        style={{
                            fontSize: config.fontSize,
                            x: v_x,
                            scale: v_scale,
                            opacity: v_opacity,
                            transformOrigin: "center center",
                        }}
                    >
                        v
                    </motion.span>

                    <motion.span
                        className="font-semibold text-foreground inline-block will-change-transform"
                        style={{
                            fontSize: config.fontSize,
                            x: e_x,
                            scale: e_scale,
                            opacity: e_opacity,
                            transformOrigin: "center center",
                        }}
                    >
                        e
                    </motion.span>

                    <motion.span
                        className="font-semibold text-foreground inline-block will-change-transform"
                        style={{
                            fontSize: config.fontSize,
                            x: l_x,
                            scale: l_scale,
                            opacity: l_opacity,
                            transformOrigin: "center center",
                        }}
                    >
                        l
                    </motion.span>

                    <motion.span
                        className="font-semibold text-foreground inline-block will-change-transform"
                        style={{
                            fontSize: config.fontSize,
                            x: a_x,
                            scale: a_scale,
                            opacity: a_opacity,
                            transformOrigin: "center center",
                        }}
                    >
                        a
                    </motion.span>
                </div>
            </div>
        </div>
    )
}
