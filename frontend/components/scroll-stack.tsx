"use client";

import React, { useEffect, useRef, useCallback } from 'react';
import type { ReactNode } from 'react';

export interface ScrollStackItemProps {
    itemClassName?: string;
    children: ReactNode;
}

export const ScrollStackItem: React.FC<ScrollStackItemProps> = ({ children, itemClassName = '' }) => (
    <div className={`scroll-stack-card ${itemClassName}`.trim()}>
        {children}
    </div>
);

interface ScrollStackProps {
    className?: string;
    children: ReactNode;
}

/**
 * Scroll Stack - Cards stack ON TOP of each other (not behind)
 * 
 * Behavior:
 * 1. Section locks when it enters viewport
 * 2. First card is centered and visible
 * 3. Small delay, then next card slides up from bottom
 * 4. New card positions ON TOP of previous card
 * 5. Repeat until all cards are stacked
 * 6. Whole stack exits upward
 * 7. Section unlocks and continues scrolling
 */
const ScrollStack: React.FC<ScrollStackProps> = ({
    children,
    className = '',
}) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const cardsRef = useRef<HTMLElement[]>([]);
    const rafRef = useRef<number | null>(null);
    const scrollProgressRef = useRef(0);

    const updateStackAnimation = useCallback(() => {
        if (!containerRef.current || !cardsRef.current.length) return;

        const container = containerRef.current;
        const containerRect = container.getBoundingClientRect();
        const viewportHeight = window.innerHeight;
        const cards = cardsRef.current;
        const totalCards = cards.length;

        // Calculate scroll progress through the section
        // 0 = section just entering, 1 = section exiting
        const sectionTop = containerRect.top;
        const sectionHeight = containerRect.height;

        // Section is "locked" when top is at viewport top
        const lockPoint = 0;
        const unlockPoint = -(sectionHeight - viewportHeight);

        // Normalize scroll progress (0 to 1)
        let progress = 0;
        if (sectionTop <= lockPoint && sectionTop >= unlockPoint) {
            progress = Math.abs(sectionTop - lockPoint) / Math.abs(unlockPoint - lockPoint);
        } else if (sectionTop < unlockPoint) {
            progress = 1;
        }

        scrollProgressRef.current = progress;

        // Animation phases (DRASTICALLY SLOWER):
        // Phase 1 (0-0.2): Delay - nothing happens, first card visible
        // Phase 2 (0.2-0.7): Cards stack one by one (VERY SLOW)
        // Phase 3 (0.7-1.0): Whole stack exits upward (NO FADE)

        const delayPhase = 0.2;
        const stackPhase = 0.7;
        const exitPhase = 1.0;

        // Vertical offset to show card edges (like React Bits)
        const cardOffset = -20; // pixels

        cards.forEach((card, i) => {
            if (!card) return;

            // Calculate base position with offset for stacking effect
            const baseOffsetY = -i * cardOffset;

            // First card is always visible and positioned with offset
            if (i === 0) {
                if (progress < stackPhase) {
                    // During stacking phase - stay in place at normal scale
                    card.style.transform = `translate(-50%, calc(-50% + ${baseOffsetY}px)) scale(1)`;
                    card.style.opacity = '1';
                    card.style.zIndex = String(1);
                } else {
                    // Exit phase - move up with stack (NO OPACITY CHANGE)
                    const exitProgress = (progress - stackPhase) / (exitPhase - stackPhase);
                    const exitY = -exitProgress * 120;
                    card.style.transform = `translate(-50%, calc(-50% + ${baseOffsetY}px + ${exitY}%)) scale(1)`;
                    card.style.opacity = '1'; // Keep at 1, no fade
                    card.style.zIndex = String(1);
                }
                return;
            }

            // Calculate when this card should appear (SEQUENTIAL - no overlap)
            // Each card waits for the previous to fully complete
            const cardDuration = 0.25; // Duration for one card to slide up
            const cardStartProgress = delayPhase + (i - 1) * cardDuration;
            const cardEndProgress = cardStartProgress + cardDuration;

            if (progress < cardStartProgress) {
                // Card hasn't appeared yet - hide it below
                card.style.transform = `translate(-50%, calc(-50% + 100%)) scale(1)`;
                card.style.opacity = '0';
                card.style.zIndex = String(i + 1);
            } else if (progress >= cardStartProgress && progress < cardEndProgress) {
                // Card is sliding up and stacking
                const cardProgress = (progress - cardStartProgress) / (cardEndProgress - cardStartProgress);
                // Ease out cubic for smoother physics
                const easedProgress = 1 - Math.pow(1 - cardProgress, 3);
                const slideY = 100 - (easedProgress * 100); // Slide from 100% to 0%

                // Scale effect: starts at 1.05 (larger), settles to 1.0 (normal)
                // Scale decreases in the second half of the animation for "settling" effect
                let scale = 1.0;
                if (cardProgress < 0.6) {
                    // First 60%: card is at larger scale
                    scale = 1.05;
                } else {
                    // Last 40%: scale down from 1.05 to 1.0 (settling effect)
                    const settleProgress = (cardProgress - 0.6) / 0.4;
                    scale = 1.05 - (settleProgress * 0.05);
                }

                card.style.transform = `translate(-50%, calc(-50% + ${baseOffsetY}px + ${slideY}%)) scale(${scale})`;
                card.style.opacity = '1';
                card.style.zIndex = String(i + 1);
            } else if (progress >= cardEndProgress && progress < stackPhase) {
                // Card is stacked in position at normal scale
                card.style.transform = `translate(-50%, calc(-50% + ${baseOffsetY}px)) scale(1)`;
                card.style.opacity = '1';
                card.style.zIndex = String(i + 1);
            } else {
                // Exit phase - move up with stack (NO OPACITY CHANGE)
                const exitProgress = (progress - stackPhase) / (exitPhase - stackPhase);
                const exitY = -exitProgress * 120;
                card.style.transform = `translate(-50%, calc(-50% + ${baseOffsetY}px + ${exitY}%)) scale(1)`;
                card.style.opacity = '1'; // Keep at 1, no fade
                card.style.zIndex = String(i + 1);
            }
        });
    }, []);

    useEffect(() => {
        const container = containerRef.current;
        if (!container) return;

        // Get all card elements
        const cards = Array.from(container.querySelectorAll('.scroll-stack-card')) as HTMLElement[];
        cardsRef.current = cards;

        // Setup cards with absolute positioning for stacking
        cards.forEach((card, i) => {
            card.style.position = 'absolute';
            card.style.top = '50%';
            card.style.left = '50%';
            card.style.transform = 'translate(-50%, -50%)';
            card.style.transition = 'none'; // No CSS transitions, we control everything
            card.style.willChange = 'transform, opacity';
            card.style.backfaceVisibility = 'hidden';

            // Hide all cards except first initially
            if (i > 0) {
                card.style.opacity = '0';
                card.style.transform = 'translate(-50%, -50%) translateY(120%)';
            } else {
                card.style.opacity = '1';
                card.style.transform = 'translate(-50%, -50%) translateY(0)';
            }

            card.style.zIndex = String(i + 1);
        });

        // Scroll listener with RAF throttling
        const handleScroll = () => {
            if (rafRef.current) return;
            rafRef.current = requestAnimationFrame(() => {
                updateStackAnimation();
                rafRef.current = null;
            });
        };

        window.addEventListener('scroll', handleScroll, { passive: true });
        updateStackAnimation();

        return () => {
            window.removeEventListener('scroll', handleScroll);
            if (rafRef.current) {
                cancelAnimationFrame(rafRef.current);
            }
        };
    }, [updateStackAnimation]);

    // Calculate section height based on number of cards (MUCH TALLER for slower animation)
    const childCount = React.Children.count(children);
    const sectionHeight = Math.max(300, childCount * 60); // vh units - 60vh per card for very slow scrolling

    return (
        <div
            ref={containerRef}
            className={`scroll-stack-container relative w-full ${className}`.trim()}
            style={{
                height: `${sectionHeight}vh`,
                position: 'relative',
            }}
        >
            <div className="sticky top-0 w-full h-screen flex items-center justify-center">
                <div className="relative w-full max-w-lg aspect-square">
                    {children}
                </div>
            </div>
        </div>
    );
};

export default ScrollStack;
