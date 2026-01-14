"use client";

import React, { useEffect, useRef, useCallback, useState } from "react";
import { motion, useMotionValue, useTransform, animate, useSpring, useVelocity } from "framer-motion";
import type { LucideIcon } from "lucide-react";

// Utility to darken hex color
const darkenColor = (hex: string, percent: number): string => {
    let color = hex.startsWith("#") ? hex.slice(1) : hex;
    if (color.length === 3) {
        color = color.split("").map((c) => c + c).join("");
    }
    const num = parseInt(color, 16);
    let r = (num >> 16) & 0xff;
    let g = (num >> 8) & 0xff;
    let b = num & 0xff;
    r = Math.max(0, Math.min(255, Math.floor(r * (1 - percent))));
    g = Math.max(0, Math.min(255, Math.floor(g * (1 - percent))));
    b = Math.max(0, Math.min(255, Math.floor(b * (1 - percent))));
    return "#" + ((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1).toUpperCase();
};

export interface FeatureCardData {
    icon: LucideIcon;
    title: string;
    description: string;
}

interface FeaturesFolderAnimationProps {
    features: FeatureCardData[];
    folderColor?: string;
    className?: string;
}

/**
 * Features Folder Animation - v8 CENTERED
 * 
 * Fixes:
 * - Fan spread is SYMMETRIC around folder (not just left)
 * - Grid positions properly centered
 */
export const FeaturesFolderAnimation: React.FC<FeaturesFolderAnimationProps> = ({
    features,
    folderColor = "#D8B4FE",  // Brand pink/purple
    className = "",
}) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const [dimensions, setDimensions] = useState({ width: 1200, height: 800 });

    const progress = useMotionValue(0);
    const smoothProgress = useSpring(progress, { damping: 15, stiffness: 80 }); // Physics smoothing
    const progressVelocity = useVelocity(smoothProgress);
    const folderTilt = useTransform(progressVelocity, [-0.5, 0.5], [5, -5]); // Aerodynamic tilt

    const folderBackColor = darkenColor(folderColor, 0.08);
    const totalCards = features.length;

    useEffect(() => {
        const updateDimensions = () => {
            setDimensions({
                width: window.innerWidth,
                height: window.innerHeight,
            });
        };
        updateDimensions();
        window.addEventListener("resize", updateDimensions);
        return () => window.removeEventListener("resize", updateDimensions);
    }, []);

    // SYMMETRIC FAN SPREAD - centered around folder
    const getFanPosition = useCallback((index: number) => {
        // Spread from -80° to +80° (160° total, centered at -90° which is straight up)
        const totalSpread = 160;
        const centerAngle = -90; // Straight up
        const startAngle = centerAngle - totalSpread / 2; // -170°
        const angleStep = totalSpread / Math.max(totalCards - 1, 1);
        const angleDeg = startAngle + index * angleStep;
        const angleRad = (angleDeg * Math.PI) / 180;

        // Varied radius for depth
        const baseRadius = 260;
        const radiusVariation = 35;
        const radius = baseRadius + (index % 3) * radiusVariation;

        const x = Math.cos(angleRad) * radius;
        const y = Math.sin(angleRad) * radius;

        const rotation = angleDeg + 90;

        return { x, y, rotation };
    }, [totalCards]);

    // CENTERED grid positions - matching original layout
    const getGridPosition = useCallback((index: number) => {
        // Determine columns based on viewport
        const cols = dimensions.width >= 1024 ? 3 : dimensions.width >= 768 ? 2 : 1;
        const gap = 32;

        // Calculate for max-w-6xl container (1152px max)
        const containerMaxWidth = 1152;
        const containerPadding = 48; // px-6 on both sides
        const availableWidth = Math.min(containerMaxWidth, dimensions.width - containerPadding);

        const cardWidth = (availableWidth - gap * (cols - 1)) / cols;

        const col = index % cols;
        const row = Math.floor(index / cols);

        // Calculate total grid dimensions
        const totalGridWidth = cols * cardWidth + (cols - 1) * gap;
        const totalRows = Math.ceil(totalCards / cols);
        const cardHeight = 240; // Increased height for better fit
        const totalGridHeight = totalRows * cardHeight + (totalRows - 1) * gap;

        // Center the grid in viewport
        // X: center horizontally (add half card width because we removed translateX(-50%))
        const gridStartX = -totalGridWidth / 2;
        const x = gridStartX + col * (cardWidth + gap) + cardWidth / 2;

        // Y: position centered (offset handled by container padding)
        const gridStartY = -totalGridHeight / 2 + 140; // Push down for navbar clearance
        const y = gridStartY + row * (cardHeight + gap) + cardHeight / 2;

        return { x, y, cardWidth };
    }, [dimensions, totalCards]);

    // Scroll handler
    useEffect(() => {
        const container = containerRef.current;
        if (!container) return;

        let animationFrame: number | null = null;
        let lastProgress = 0;

        const handleScroll = () => {
            if (animationFrame) return;

            animationFrame = requestAnimationFrame(() => {
                const rect = container.getBoundingClientRect();
                const viewportHeight = window.innerHeight;
                const sectionHeight = rect.height;

                const lockPoint = 0;
                const unlockPoint = -(sectionHeight - viewportHeight);

                let newProgress = 0;
                if (rect.top <= lockPoint && rect.top >= unlockPoint) {
                    newProgress = Math.abs(rect.top - lockPoint) / Math.abs(unlockPoint - lockPoint);
                } else if (rect.top < unlockPoint) {
                    newProgress = 1;
                }

                const isScrollingDown = newProgress > lastProgress;
                lastProgress = newProgress;

                animate(progress, newProgress, {
                    type: isScrollingDown ? "spring" : "tween",
                    stiffness: isScrollingDown ? 80 : undefined,
                    damping: isScrollingDown ? 25 : undefined,
                    duration: isScrollingDown ? undefined : 0.4,
                    ease: isScrollingDown ? undefined : "easeOut",
                });

                animationFrame = null;
            });
        };

        window.addEventListener("scroll", handleScroll, { passive: true });
        handleScroll();

        return () => {
            window.removeEventListener("scroll", handleScroll);
            if (animationFrame) cancelAnimationFrame(animationFrame);
        };
    }, [progress]);

    // Folder transforms
    // Phase 1: Slide Down (0.0 -> 0.3)
    // Phase 2: Open (0.3 -> 0.4)
    // Phase 3: Drift & Fade (0.5 -> 0.65)

    // Delayed OPEN until after slide
    const folderOpen = useTransform(smoothProgress, [0.3, 0.4], [0, 1]);

    // Opacity fades out later
    const folderOpacity = useTransform(smoothProgress, [0, 0.45, 0.65], [1, 1, 0]);

    // Y Position: Starts high (-200), slides to base (0), then drifts down (+100)
    const folderY = useTransform(smoothProgress, [0, 0.3, 0.5, 0.65], [-200, 0, 0, 100]);

    const folderScale = useTransform(smoothProgress, [0.3, 0.4], [1, 1.12]);

    // Ring opacity
    const ringOpacity = useTransform(smoothProgress, [0.7, 0.8, 0.95, 1.0], [0, 0.25, 0.25, 0]);



    // Card transforms - SEAMLESS from folder → fan → grid
    const cardTransforms = features.map((_, index) => {
        const fanPos = getFanPosition(index);
        const gridPos = getGridPosition(index);

        // Phase timing - Shifted for slide phase
        const dealDelay = index * 0.015;
        const emergeStart = 0.35 + dealDelay; // Starts after folder opens
        const emergeEnd = emergeStart + 0.16;
        const floatEnd = 0.65;
        const gridStart = 0.65;
        const gridEnd = 1.0;

        // Emergence from folder center
        const emergeProgress = useTransform(progress, [emergeStart, emergeEnd], [0, 1]);

        const emergeX = useTransform(emergeProgress,
            [0, 0.25, 0.55, 0.85, 1],
            [0, fanPos.x * 0.08, fanPos.x * 0.35, fanPos.x * 0.75, fanPos.x]
        );
        const emergeY = useTransform(emergeProgress,
            [0, 0.2, 0.45, 0.75, 1],
            [240, 140, -60, fanPos.y * 0.5 - 30, fanPos.y]
        );

        // Start VERY small
        const emergeScale = useTransform(emergeProgress,
            [0, 0.15, 0.35, 0.6, 0.85, 1],
            [0.05, 0.15, 0.35, 0.6, 0.85, 1]
        );

        const emergeOpacity = useTransform(emergeProgress, [0, 0.08, 0.25], [0, 0.5, 1]);
        const emergeRotation = useTransform(emergeProgress, [0, 0.5, 1], [0, fanPos.rotation * 0.6, fanPos.rotation * 0.35]);

        // Grid fly phase
        const gridProgress = useTransform(smoothProgress, [gridStart, gridEnd], [0, 1]);

        const easeInOutQuart = (t: number) => t < 0.5 ? 8 * t * t * t * t : 1 - Math.pow(-2 * t + 2, 4) / 2;

        // Combined transforms
        const x = useTransform(progress, (p) => {
            if (p < emergeEnd) return emergeX.get();
            if (p < gridStart) {
                const wobble = Math.sin(((p - emergeEnd) / (gridStart - emergeEnd)) * Math.PI * 3 + index) * 4;
                return fanPos.x + wobble;
            }
            const gp = easeInOutQuart(gridProgress.get());
            return fanPos.x + (gridPos.x - fanPos.x) * gp;
        });

        const y = useTransform(progress, (p) => {
            if (p < emergeEnd) return emergeY.get();
            if (p < gridStart) {
                const bob = Math.sin(((p - emergeEnd) / (gridStart - emergeEnd)) * Math.PI * 2 + index * 0.7) * 6;
                return fanPos.y + bob;
            }
            const gp = easeInOutQuart(gridProgress.get());
            return fanPos.y + (gridPos.y - fanPos.y) * gp;
        });

        const scale = useTransform(progress, (p) => {
            if (p < emergeEnd) return emergeScale.get();
            if (p < gridStart) return 1;
            const gp = gridProgress.get();
            if (gp > 0.9) {
                const bounce = Math.sin((gp - 0.9) / 0.1 * Math.PI) * 0.015;
                return 1 + bounce;
            }
            return 1;
        });

        const opacity = useTransform(progress, (p) => {
            if (p < emergeStart) return 0;
            if (p < emergeEnd) return emergeOpacity.get();
            return 1;
        });

        const rotation = useTransform(progress, (p) => {
            if (p < emergeEnd) return emergeRotation.get();
            if (p < gridStart) return fanPos.rotation * 0.35;
            const gp = easeInOutQuart(gridProgress.get());
            return fanPos.rotation * 0.35 * (1 - gp);
        });

        return { x, y, scale, opacity, rotation, cardWidth: gridPos.cardWidth };
    });

    const sectionHeight = 450;

    return (
        <>
            {/* Desktop Animation */}
            <div
                ref={containerRef}
                className={`relative w-full hidden md:block ${className}`.trim()}
                style={{ height: `${sectionHeight}vh` }}
            >
                <div className="sticky top-0 w-full h-screen">
                    {/* Folder BACK (Body + Tab) */}
                    <motion.div
                        className="absolute left-1/2 pointer-events-none"
                        style={{
                            top: "calc(50% + 140px)",
                            x: "-50%",
                            y: folderY,
                            rotate: folderTilt,
                            scale: folderScale,
                            opacity: folderOpacity,
                            zIndex: 1, // Behind cards
                        } as any}
                    >
                        <div
                            style={{
                                width: "300px",
                                height: "240px",
                                backgroundColor: folderBackColor,
                                background: `linear-gradient(180deg, ${folderBackColor} 0%, ${darkenColor(folderBackColor, 0.2)} 100%)`,
                                borderRadius: "0 30px 30px 30px",
                                position: "relative",
                                border: "1px solid rgba(255,255,255,0.05)",
                                boxShadow: "0 20px 40px -10px rgba(0,0,0,0.3)",
                            }}
                        >
                            <span
                                style={{
                                    position: "absolute",
                                    bottom: "98%",
                                    left: 0,
                                    width: "90px",
                                    height: "30px",
                                    backgroundColor: folderBackColor,
                                    borderRadius: "15px 15px 0 0",
                                    border: "1px solid rgba(255,255,255,0.05)",
                                    borderBottom: "none",
                                }}
                            />
                        </div>
                    </motion.div>

                    {/* Offset content down to match folder position */}
                    <div className="absolute inset-0 flex items-center justify-center">
                        {/* Ring containers */}
                        {features.map((_, index) => {
                            const gridPos = getGridPosition(index);
                            return (
                                <motion.div
                                    key={`ring-${index}`}
                                    className="absolute pointer-events-none"
                                    style={{
                                        width: `${gridPos.cardWidth + 12}px`,
                                        height: "192px",
                                        border: "2px dashed",
                                        borderColor: "var(--border)",
                                        borderRadius: "18px",
                                        opacity: ringOpacity,
                                        x: gridPos.x,
                                        y: gridPos.y,
                                    }}
                                />
                            );
                        })}

                        {/* Feature cards */}
                        {features.map((feature, index) => {
                            const t = cardTransforms[index];
                            return (
                                <motion.div
                                    key={`card-${index}`}
                                    className="absolute group bg-card rounded-2xl border border-border/50 hover:border-border hover:shadow-lg hover:shadow-muted/50 transition-colors duration-300 p-8"
                                    style={{
                                        width: `${t.cardWidth}px`,
                                        x: t.x,
                                        y: t.y,
                                        scale: t.scale,
                                        opacity: t.opacity,
                                        rotate: t.rotation,
                                        zIndex: 10 + (totalCards - index), // Middle layer
                                    }}
                                >
                                    <motion.div
                                        whileHover={{ scale: 1.05 }}
                                        transition={{ duration: 0.2 }}
                                        className="w-12 h-12 rounded-xl bg-muted flex items-center justify-center mb-6 group-hover:bg-accent/30 transition-colors"
                                    >
                                        <feature.icon className="w-5 h-5 text-foreground" />
                                    </motion.div>
                                    <h3 className="text-lg font-medium mb-2">{feature.title}</h3>
                                    <p className="text-sm text-muted-foreground leading-relaxed">
                                        {feature.description}
                                    </p>
                                </motion.div>
                            );
                        })}
                    </div>

                    {/* Folder FRONT (Flaps) */}
                    <motion.div
                        className="absolute left-1/2 pointer-events-none"
                        style={{
                            top: "calc(50% + 140px)",
                            x: "-50%",
                            y: folderY,
                            rotate: folderTilt,
                            scale: folderScale,
                            opacity: folderOpacity,
                            zIndex: 100, // In front of cards
                            "--folder-open": folderOpen,
                        } as any}
                    >
                        <div
                            style={{
                                width: "300px",
                                height: "240px",
                                backgroundColor: "transparent", // Transparent body
                                borderRadius: "0 30px 30px 30px",
                                position: "relative",
                            }}
                        >
                            {/* Note: Tab removed from front layer */}

                            <motion.div
                                style={{
                                    position: "absolute",
                                    width: "100%",
                                    height: "100%",
                                    backgroundColor: folderColor,
                                    background: `linear-gradient(135deg, ${folderColor} 0%, ${darkenColor(folderColor, 0.1)} 100%)`,
                                    borderRadius: "15px 30px 30px 30px",
                                    border: "1px solid rgba(255,255,255,0.1)",
                                    boxShadow: "inset 0 1px 1px rgba(255,255,255,0.3), 0 -5px 10px rgba(0,0,0,0.1)", // Depth
                                    transformOrigin: "bottom",
                                    skewX: useTransform(folderOpen, [0, 1], [0, 24]),
                                    scaleY: useTransform(folderOpen, [0, 1], [1, 0.4]),
                                }}
                            />
                            <motion.div
                                style={{
                                    position: "absolute",
                                    width: "100%",
                                    height: "100%",
                                    backgroundColor: folderColor,
                                    background: `linear-gradient(to bottom right, ${folderColor}, ${darkenColor(folderColor, 0.05)})`,
                                    borderRadius: "15px 30px 30px 30px",
                                    border: "1px solid rgba(255,255,255,0.1)",
                                    borderLeft: "1px solid rgba(255,255,255,0.2)", // Highlight
                                    transformOrigin: "bottom",
                                    skewX: useTransform(folderOpen, [0, 1], [0, -24]),
                                    scaleY: useTransform(folderOpen, [0, 1], [1, 0.4]),
                                }}
                            />
                        </div>
                    </motion.div>
                </div>
            </div>

            {/* Mobile Static View */}
            <div className={`w-full md:hidden py-12 px-6 ${className}`.trim()}>
                <div className="grid grid-cols-1 gap-6">
                    {features.map((feature, index) => (
                        <div key={index} className="bg-card rounded-2xl border border-border/50 p-6 shadow-sm">
                            <div className="w-12 h-12 rounded-xl bg-muted flex items-center justify-center mb-4">
                                <feature.icon className="w-5 h-5 text-foreground" />
                            </div>
                            <h3 className="text-lg font-medium mb-2">{feature.title}</h3>
                            <p className="text-sm text-muted-foreground leading-relaxed">
                                {feature.description}
                            </p>
                        </div>
                    ))}
                </div>
            </div>
        </>
    );
};

export default FeaturesFolderAnimation;
