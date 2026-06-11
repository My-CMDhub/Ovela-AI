"use client"

import { useRef, useState } from "react"
import { motion, useScroll, useTransform, useSpring, useMotionTemplate } from "framer-motion"
import { CheckCircle2 } from "lucide-react"
import { cn } from "@/lib/utils"

interface ValueProp {
    icon?: React.ReactNode
    title: string
    description: string
}

interface PremiumFeaturesProps {
    features: ValueProp[]
}

export function PremiumFeatures({ features }: PremiumFeaturesProps) {
    if (!features || features.length < 3) return null

    return (
        <div className="w-full py-24 lg:py-32 relative">
            <div className="max-w-7xl mx-auto px-6">
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 lg:gap-8 auto-rows-[minmax(300px,auto)]">
                    {/* Feature 1 - Large Editorial Card (Span 7) */}
                    <FeatureCard
                        feature={features[0]}
                        className="lg:col-span-7 lg:row-span-1 min-h-[400px]"
                        index={0}
                        variant="primary"
                    />

                    {/* Feature 2 - Vertical Focus (Span 5) */}
                    <FeatureCard
                        feature={features[1]}
                        className="lg:col-span-5 lg:row-span-1 min-h-[400px]"
                        index={1}
                        variant="secondary"
                    />

                    {/* Feature 3 - Wide Cinematic (Span 12) */}
                    <FeatureCard
                        feature={features[2]}
                        className="lg:col-span-12 lg:row-span-1 min-h-[350px]"
                        index={2}
                        variant="wide"
                    />
                </div>
            </div>
        </div>
    )
}

function FeatureCard({
    feature,
    className,
    index,
    variant = "primary"
}: {
    feature: ValueProp
    className?: string
    index: number
    variant?: "primary" | "secondary" | "wide"
}) {
    const cardRef = useRef<HTMLDivElement>(null)
    const [isHovered, setIsHovered] = useState(false)

    // Mouse follow effect for internal glow
    const { scrollYProgress } = useScroll({
        target: cardRef,
        offset: ["start end", "end start"]
    })

    // Parallax for text/content
    const yContent = useTransform(scrollYProgress, [0, 1], [0, variant === 'secondary' ? -20 : 0])

    // Icon animation state (draws when in view)
    const iconDrag = useSpring(0, { stiffness: 100, damping: 30 })

    return (
        <motion.div
            ref={cardRef}
            initial={{ opacity: 0, y: 50, filter: "blur(10px)" }}
            whileInView={{ opacity: 1, y: 0, filter: "blur(0px)" }}
            viewport={{ once: true, margin: "-10%" }}
            transition={{ duration: 0.8, delay: index * 0.15, ease: [0.215, 0.61, 0.355, 1.0] }}
            className={cn(
                "group relative overflow-hidden rounded-[2rem] bg-[#0a0a0a] border border-white/5",
                "hover:border-white/10 transition-colors duration-500",
                className
            )}
            onMouseEnter={() => setIsHovered(true)}
            onMouseLeave={() => setIsHovered(false)}
        >
            {/* Ambient Background Gradient (Subtle) */}
            <div className="absolute inset-0 bg-gradient-to-br from-white/[0.03] to-transparent opacity-100 transition-opacity duration-500" />

            {/* Hover Spotlight Glow */}
            <MouseGlow />

            <div className="relative h-full flex flex-col p-8 md:p-12 z-20">
                {/* Header Section */}
                <div className="flex justify-between items-start mb-auto">
                    <motion.div
                        className="p-3 rounded-full bg-white/5 border border-white/10 text-white/90 backdrop-blur-md"
                        whileHover={{ scale: 1.1, backgroundColor: "rgba(255,255,255,0.1)" }}
                    >
                        {/* Render Icon with cloned element to control size if needed, or wrap */}
                        <div className="w-6 h-6 md:w-8 md:h-8">
                            {feature.icon || <CheckCircle2 className="w-full h-full" />}
                        </div>
                    </motion.div>

                    <span className="text-xs font-mono text-white/30 uppercase tracking-widest">
                        0{index + 1}
                    </span>
                </div>

                {/* Content Section */}
                <motion.div style={{ y: yContent }} className="mt-8 md:mt-12">
                    <h3 className={cn(
                        "font-serif text-3xl md:text-5xl text-white mb-6 leading-[0.9] tracking-tight",
                        "group-hover:text-white/90 transition-colors"
                    )}>
                        {feature.title.split(" ").map((word, i) => (
                            <span key={i} className="inline-block mr-2 lg:block lg:mr-0">
                                {word}
                            </span>
                        ))}
                    </h3>

                    <div className="relative overflow-hidden">
                        <p className="text-lg md:text-xl text-white/50 leading-relaxed max-w-xl group-hover:text-white/70 transition-colors duration-500">
                            {feature.description}
                        </p>

                        {/* Animated Line reveal on hover */}
                        <motion.div
                            className="absolute bottom-0 left-0 h-[1px] bg-white/30 w-full origin-left"
                            initial={{ scaleX: 0 }}
                            animate={{ scaleX: isHovered ? 1 : 0 }}
                            transition={{ duration: 0.6, ease: "circOut" }}
                        />
                    </div>
                </motion.div>

                {/* Decorative Elements */}
                {variant === 'wide' && (
                    <div className="absolute right-0 top-0 bottom-0 w-1/3 bg-gradient-to-l from-white/[0.02] to-transparent pointer-events-none hidden lg:block" />
                )}
            </div>
        </motion.div>
    )
}

function MouseGlow() {
    return (
        <div className="absolute inset-0 overflow-hidden pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity duration-700">
            <div className="absolute -inset-[100%] bg-[radial-gradient(circle_400px_at_center,rgba(255,255,255,0.06),transparent)] group-hover:translate-x-0 transition-transform duration-0" />
        </div>
    )
}
