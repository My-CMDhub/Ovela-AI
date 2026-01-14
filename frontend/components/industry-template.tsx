"use client"

import { motion } from "framer-motion"
import { ArrowRight, CheckCircle2 } from "lucide-react"
import Link from "next/link"
import { ReactNode } from "react"
import { Footer } from "@/components/footer"
import { Header } from "@/components/header"
import { FrictionList } from "@/components/friction-list"
import { AmbientBackground } from "@/components/ui/ambient-background"

import TrueFocus from "@/components/ui/true-focus"
import ScrollStack, { ScrollStackItem } from "@/components/scroll-stack"

interface PainPoint {
    label: string
    problem: string
}

interface ValueProp {
    icon?: ReactNode
    title: string
    description: string
}

interface IndustryTemplateProps {
    industry: string
    heroTitle: ReactNode
    heroSubtitle?: string
    heroFocusSentence?: string // New optional prop for formatted animation
    painPoints: PainPoint[]
    valueProps: ValueProp[]
    workflowTitle?: string
    workflowDescription?: string
    ctaText?: string
    ctaHref?: string
    heroVisual?: ReactNode
}

export function IndustryTemplate({
    industry,
    heroTitle,
    heroSubtitle,
    heroFocusSentence,
    painPoints,
    valueProps,
    workflowTitle = "The Workflow",
    workflowDescription = "Seamless integration with your existing operations.",
    ctaText = "Deploy for " + industry,
    ctaHref = "/#contact",
    heroVisual,
}: IndustryTemplateProps) {
    return (
        <div className="min-h-screen bg-background selection:bg-primary/20">
            <Header />

            <main className="pt-24 pb-20">
                {/* Hero Section */}
                <section className="relative px-6 lg:px-12 py-12 md:py-20 max-w-7xl mx-auto">
                    <div className={`flex flex-col ${heroVisual ? 'lg:flex-row lg:items-center lg:text-left text-center gap-12' : 'items-center text-center'}`}>

                        <motion.div
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ duration: 0.6 }}
                            className={heroVisual ? 'lg:flex-1' : 'w-full'}
                        >
                            <span className="inline-block px-3 py-1 mb-6 text-xs font-medium tracking-widest text-muted-foreground uppercase border border-border rounded-full">
                                {industry}
                            </span>
                            <h1 className="font-serif text-5xl md:text-7xl font-medium tracking-tight text-foreground max-w-4xl mb-6">
                                {heroTitle}
                            </h1>


                            {heroFocusSentence && (
                                <div className="mb-6 min-h-[4rem] flex items-center justify-center lg:justify-start">
                                    <TrueFocus
                                        sentence={heroFocusSentence}
                                        manualMode={false}
                                        blurAmount={6}
                                        borderColor="var(--accent)"
                                        glowColor="var(--accent)"
                                        animationDuration={0.5}
                                        pauseBetweenAnimations={1.5}
                                    />
                                </div>
                            )}

                            {heroSubtitle && (
                                <p className="text-xl text-muted-foreground max-w-2xl leading-relaxed mb-8">
                                    {heroSubtitle}
                                </p>
                            )}
                        </motion.div>

                        {heroVisual && (
                            <motion.div
                                initial={{ opacity: 0, scale: 0.95 }}
                                animate={{ opacity: 1, scale: 1 }}
                                transition={{ duration: 0.8, delay: 0.2 }}
                                className="lg:flex-1 w-full flex justify-center lg:justify-end"
                            >
                                {heroVisual}
                            </motion.div>
                        )}

                    </div>
                </section>

                {/* The Friction (Pain Points) - REDESIGNED */}
                <section className="px-6 lg:px-12 py-12 md:py-24 bg-muted/20 border-y border-border/40">
                    <div className="max-w-7xl mx-auto flex flex-col md:flex-row gap-16 items-start">
                        <div className="md:w-1/3 md:sticky md:top-32">
                            <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-4 flex items-center gap-2">
                                <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse"></span>
                                Operational Friction
                            </h3>
                            <p className="text-4xl md:text-5xl font-serif font-medium text-foreground leading-tight mb-6">
                                Where revenue <br /> <span className="italic text-muted-foreground">leaks.</span>
                            </p>
                            <p className="text-lg text-muted-foreground leading-relaxed">
                                Identify the silent inefficiencies draining your daily operations.
                            </p>
                        </div>
                        <div className="md:w-2/3 w-full">
                            <FrictionList items={painPoints} />
                        </div>
                    </div>
                </section>

                {/* The Solution (Scroll Stack Workflow) */}
                <section className="relative w-full bg-background border-t border-border/20">
                    <div className="max-w-7xl mx-auto flex flex-col lg:flex-row">

                        {/* Left: Sticky Heading & Context */}
                        <div className="w-full lg:w-1/2 p-6 lg:p-12 lg:h-screen lg:sticky lg:top-0 flex flex-col justify-center border-b lg:border-b-0 lg:border-r border-border/20 bg-background z-10">
                            <h2 className="text-4xl md:text-5xl font-serif font-medium mb-6 text-foreground leading-tight">
                                {workflowTitle}
                            </h2>
                            <p className="text-xl text-muted-foreground leading-relaxed mb-8 max-w-md">
                                {workflowDescription}
                            </p>
                            <div>
                                <Link
                                    href={ctaHref}
                                    className="inline-flex items-center text-primary text-lg font-medium hover:underline underline-offset-4"
                                >
                                    {ctaText} <ArrowRight className="ml-2 w-5 h-5" />
                                </Link>
                            </div>
                        </div>

                        {/* Right: Scroll Stack Animation */}
                        <div className="w-full lg:w-1/2 bg-background">
                            <ScrollStack>
                                {valueProps.map((prop, idx) => (
                                    <ScrollStackItem key={idx} itemClassName="bg-card/80 backdrop-blur-xl border-2 border-border/50 shadow-[0_8px_30px_rgb(0,0,0,0.12),0_2px_8px_rgb(0,0,0,0.08)] dark:shadow-[0_8px_30px_rgb(0,0,0,0.4),0_2px_8px_rgb(0,0,0,0.3)] ring-1 ring-foreground/5 w-full h-full flex flex-col justify-center p-8 rounded-3xl">
                                        <div className="w-14 h-14 rounded-full bg-primary/20 flex items-center justify-center text-primary mb-6">
                                            {prop.icon || <CheckCircle2 size={28} />}
                                        </div>
                                        <h3 className="text-2xl md:text-3xl font-medium text-foreground mb-4 leading-tight">{prop.title}</h3>
                                        <p className="text-lg text-muted-foreground leading-relaxed">
                                            {prop.description}
                                        </p>
                                    </ScrollStackItem>
                                ))}
                            </ScrollStack>
                        </div>

                    </div>
                </section>

                {/* Footer CTA with Ambient Background */}
                <section className="relative py-20 md:py-32 border-t border-border overflow-hidden">
                    <AmbientBackground />
                    <div className="relative z-10 max-w-4xl mx-auto px-6 text-center">
                        <motion.h2
                            initial="hidden"
                            whileInView="visible"
                            viewport={{ once: true, margin: "-100px" }}
                            className="text-4xl md:text-6xl font-serif font-medium mb-8 tracking-tight text-foreground"
                        >
                            {["Built for operators,", "not marketers."].map((line, lineIdx) => (
                                <span key={lineIdx} className="block">
                                    {line.split("").map((char, charIdx) => (
                                        <motion.span
                                            key={charIdx}
                                            variants={{
                                                hidden: { opacity: 0, y: 10 },
                                                visible: { opacity: 1, y: 0 }
                                            }}
                                            transition={{
                                                duration: 0.4,
                                                delay: (lineIdx * 20 + charIdx) * 0.02,
                                                ease: [0.215, 0.61, 0.355, 1.0]
                                            }}
                                            className="inline-block"
                                            style={{ whiteSpace: char === " " ? "pre" : "normal" }}
                                        >
                                            {char}
                                        </motion.span>
                                    ))}
                                </span>
                            ))}
                        </motion.h2>
                        <p className="text-lg md:text-xl text-muted-foreground mb-10 max-w-xl mx-auto">
                            We deploy systems that work quietly in the background. No hype, just handled calls.
                        </p>
                        <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                            <Link
                                href={ctaHref}
                                className="inline-flex h-12 items-center justify-center rounded-full bg-primary px-8 text-base font-medium text-primary-foreground shadow-lg shadow-primary/20 transition-all hover:bg-primary/90 hover:scale-105"
                            >
                                Start Deployment
                            </Link>
                            <Link
                                href="/"
                                className="inline-flex h-12 items-center justify-center rounded-full border border-input bg-background/50 backdrop-blur-sm px-8 text-base font-medium shadow-sm transition-colors hover:bg-accent hover:text-accent-foreground"
                            >
                                View Live Demo
                            </Link>
                        </div>
                    </div>
                </section>
            </main>

            <Footer />
        </div >
    )
}
