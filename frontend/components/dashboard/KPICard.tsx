"use client";

import { LucideIcon } from "lucide-react";
import { useTheme } from "@/contexts/ThemeContext";
import { motion } from "framer-motion";

interface KPICardProps {
    title: string;
    value: string | number;
    icon: LucideIcon;
    subtitle?: string;
    trend?: "up" | "down" | "neutral";
}

export default function KPICard({ title, value, icon: Icon, subtitle }: KPICardProps) {
    const { industry, theme } = useTheme();

    // === BEAUTY: Glassmorphism with hover glow ===
    if (industry === "beauty") {
        return (
            <motion.div
                whileHover={{ scale: 1.02, y: -4 }}
                transition={{ type: "spring", stiffness: 300, damping: 20 }}
                className="glass-panel rounded-2xl p-6 relative overflow-hidden group cursor-pointer"
            >
                {/* Gradient Glow on Hover */}
                <div className="absolute inset-0 bg-gradient-to-br from-primary/10 via-transparent to-accent/10 opacity-0 group-hover:opacity-100 transition-opacity duration-500" />

                <div className="relative z-10 flex items-start justify-between">
                    <div>
                        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">{title}</p>
                        <p className="text-4xl font-bold text-foreground mt-2 tracking-tight font-serif">{value}</p>
                        {subtitle && (
                            <div className="flex items-center gap-1.5 mt-3">
                                <div className="w-2 h-2 rounded-full bg-primary animate-pulse" />
                                <p className="text-xs text-muted-foreground">{subtitle}</p>
                            </div>
                        )}
                    </div>
                    <div className="p-3 rounded-xl bg-gradient-to-br from-primary/20 to-accent/20 text-primary group-hover:scale-110 transition-transform duration-300">
                        <Icon className="w-5 h-5" />
                    </div>
                </div>
            </motion.div>
        );
    }

    // === FITNESS: Dark/Neon with bold typography ===
    if (industry === "fitness") {
        return (
            <motion.div
                whileHover={{ scale: 1.03 }}
                transition={{ type: "spring", stiffness: 400 }}
                className="bg-card border-2 border-primary/30 rounded-xl p-6 relative overflow-hidden group"
            >
                {/* Neon Glow Border Effect */}
                <div className="absolute inset-0 rounded-xl opacity-0 group-hover:opacity-100 transition-opacity duration-300"
                    style={{ boxShadow: '0 0 20px var(--primary), inset 0 0 20px rgba(var(--primary), 0.1)' }} />

                <div className="relative z-10 flex items-start justify-between">
                    <div>
                        <p className="text-xs font-bold text-primary uppercase tracking-widest">{title}</p>
                        <p className="text-5xl font-black text-foreground mt-2 tracking-tighter italic">{value}</p>
                        {subtitle && (
                            <div className="flex items-center gap-2 mt-3">
                                <div className="h-1 w-8 bg-primary rounded-full" />
                                <p className="text-xs text-muted-foreground font-semibold uppercase">{subtitle}</p>
                            </div>
                        )}
                    </div>
                    <div className="p-3 rounded-lg bg-primary text-primary-foreground group-hover:neon-glow transition-all duration-300">
                        <Icon className="w-6 h-6" />
                    </div>
                </div>
            </motion.div>
        );
    }

    // === PROFESSIONAL: Minimal, Data-Dense, Executive ===
    if (industry === "professional") {
        return (
            <div className="bg-card border border-border rounded-md p-5 shadow-none hover:shadow-sm transition-shadow">
                <div className="flex items-start justify-between">
                    <div className="flex-1">
                        <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">{title}</p>
                        <p className="text-2xl font-bold text-foreground mt-1.5 tracking-tight">{value}</p>
                        {subtitle && (
                            <p className="text-[11px] text-muted-foreground mt-1.5">{subtitle}</p>
                        )}
                    </div>
                    <div className="p-2 rounded bg-primary/10 text-primary">
                        <Icon className="w-4 h-4" />
                    </div>
                </div>
            </div>
        );
    }

    // === HOSPITALITY: Warm, Luxe, Inviting ===
    if (industry === "hospitality") {
        return (
            <motion.div
                whileHover={{ y: -2 }}
                transition={{ type: "spring", stiffness: 300 }}
                className="bg-gradient-to-br from-card to-secondary/20 border border-border rounded-2xl p-6 shadow-md relative overflow-hidden"
            >
                {/* Warm Glow */}
                <div className="absolute top-0 right-0 w-32 h-32 bg-primary/10 rounded-full blur-3xl" />

                <div className="relative z-10 flex items-start justify-between">
                    <div>
                        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">{title}</p>
                        <p className="text-3xl font-bold text-foreground mt-2 tracking-tight">{value}</p>
                        {subtitle && (
                            <div className="flex items-center gap-1.5 mt-2">
                                <div className="w-1.5 h-1.5 rounded-full bg-primary" />
                                <p className="text-xs text-muted-foreground">{subtitle}</p>
                            </div>
                        )}
                    </div>
                    <div className="p-3 rounded-xl bg-primary/20 text-primary">
                        <Icon className="w-5 h-5" />
                    </div>
                </div>
            </motion.div>
        );
    }

    // === RETAIL: Editorial, Bold, High-Contrast ===
    if (industry === "retail") {
        return (
            <div className="bg-card border-2 border-foreground/10 rounded p-6 hover:border-foreground/30 transition-colors">
                <div className="flex items-start justify-between">
                    <div>
                        <p className="text-[10px] font-black text-foreground uppercase tracking-[0.2em]">{title}</p>
                        <p className="text-5xl font-black text-foreground mt-2 tracking-tighter">{value}</p>
                        {subtitle && (
                            <p className="text-xs text-muted-foreground mt-2 font-medium">{subtitle}</p>
                        )}
                    </div>
                    <div className="p-2.5 rounded-none bg-foreground text-background">
                        <Icon className="w-5 h-5" />
                    </div>
                </div>
            </div>
        );
    }

    // === HEALTH/MEDICAL: Clean, Clinical, Solid (Default) ===
    return (
        <div className="bg-card border border-border rounded-lg p-6 shadow-sm relative overflow-hidden">
            {/* Clinical Top Border Accent */}
            <div className="absolute top-0 left-0 w-full h-1 bg-primary/20" />

            <div className="flex items-start justify-between">
                <div>
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">{title}</p>
                    <p className="text-3xl font-bold text-foreground mt-2 tracking-tight">{value}</p>
                    {subtitle && (
                        <div className="flex items-center gap-1.5 mt-2">
                            <div className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                            <p className="text-xs text-muted-foreground font-medium">{subtitle}</p>
                        </div>
                    )}
                </div>
                <div className="p-2.5 rounded-md bg-secondary text-primary">
                    <Icon className="w-5 h-5" />
                </div>
            </div>
        </div>
    );
}
