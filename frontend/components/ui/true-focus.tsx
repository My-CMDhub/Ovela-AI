import { useEffect, useRef, useState, useMemo } from 'react';
import { motion } from 'framer-motion';
import { DecodingText } from './decoding-text';

interface TrueFocusProps {
    sentence?: string;
    separator?: string;
    manualMode?: boolean;
    blurAmount?: number;
    borderColor?: string;
    glowColor?: string;
    animationDuration?: number;
    pauseBetweenAnimations?: number;
}

interface FocusRect {
    x: number;
    y: number;
    width: number;
    height: number;
}

const TrueFocus: React.FC<TrueFocusProps> = ({
    sentence = 'True Focus',
    separator = ' ',
    manualMode = false,
    blurAmount = 5,
    borderColor = 'green',
    glowColor = 'rgba(0, 255, 0, 0.6)',
    animationDuration = 0.5,
    pauseBetweenAnimations = 1
}) => {
    // Parse sentence into variants: "A|B C|D" -> [["A", "B"], ["C", "D"]]
    const wordVariants = useMemo(() => {
        return sentence.split(separator).map(part => {
            // Strip outer braces if present: "{A|B}" -> "A|B"
            return part.replace(/^\{|\}$/g, '').split('|').map(w => w.trim());
        });
    }, [sentence, separator]);

    const [currentIndex, setCurrentIndex] = useState<number>(0);
    const [lastActiveIndex, setLastActiveIndex] = useState<number | null>(null);
    const [variantIndices, setVariantIndices] = useState<number[]>(() => wordVariants.map(() => 0));

    const containerRef = useRef<HTMLDivElement | null>(null);
    const wordRefs = useRef<(HTMLSpanElement | null)[]>([]);
    const [focusRect, setFocusRect] = useState<FocusRect>({ x: 0, y: 0, width: 0, height: 0 });
    const prevIndexRef = useRef(currentIndex);

    // Auto-cycle focus
    useEffect(() => {
        if (!manualMode) {
            const interval = setInterval(
                () => {
                    setCurrentIndex(prev => (prev + 1) % wordVariants.length);
                },
                (animationDuration + pauseBetweenAnimations) * 1000
            );

            return () => clearInterval(interval);
        }
    }, [manualMode, animationDuration, pauseBetweenAnimations, wordVariants.length]);

    // Handle word cycling on blur (when focus moves away)
    useEffect(() => {
        if (currentIndex !== prevIndexRef.current) {
            const prevIndex = prevIndexRef.current;
            // Cycle the word that just lost focus
            setVariantIndices(prev => {
                const newIndices = [...prev];
                if (wordVariants[prevIndex] && wordVariants[prevIndex].length > 1) {
                    newIndices[prevIndex] = (newIndices[prevIndex] + 1) % wordVariants[prevIndex].length;
                }
                return newIndices;
            });
            prevIndexRef.current = currentIndex;
        }
    }, [currentIndex, wordVariants]);

    // Update Focus Rect using ResizeObserver to handle dynamic text changes
    useEffect(() => {
        if (currentIndex === null || currentIndex === -1) return;
        const activeEl = wordRefs.current[currentIndex];
        if (!activeEl || !containerRef.current) return;

        const updateRect = () => {
            if (!activeEl || !containerRef.current) return;

            const parentRect = containerRef.current.getBoundingClientRect();
            const activeRect = activeEl.getBoundingClientRect();

            setFocusRect({
                x: (activeRect.left - parentRect.left) - 15,
                y: (activeRect.top - parentRect.top) - 15,
                width: activeRect.width + 30,
                height: activeRect.height + 30
            });
        };

        // Initial measure
        updateRect();

        // Observe size changes (crucial for decoding animation)
        const observer = new ResizeObserver(updateRect);
        observer.observe(activeEl);

        return () => observer.disconnect();
    }, [currentIndex, variantIndices, wordVariants.length]); // Re-attach observer when focus changes

    const handleMouseEnter = (index: number) => {
        if (manualMode) {
            setLastActiveIndex(index);
            setCurrentIndex(index);
        }
    };

    const handleMouseLeave = () => {
        if (manualMode) {
            setCurrentIndex(lastActiveIndex!);
        }
    };

    return (
        <div
            className="relative flex flex-col md:flex-row gap-6 justify-center items-center flex-wrap"
            ref={containerRef}
            style={{ outline: 'none', userSelect: 'none' }}
        >
            {wordVariants.map((variants, index) => {
                const isActive = index === currentIndex;
                const currentText = variants[variantIndices[index] % variants.length];

                return (
                    <span
                        key={index}
                        ref={el => {
                            wordRefs.current[index] = el;
                        }}
                        className="relative text-[3rem] font-black cursor-pointer"
                        style={
                            {
                                filter: manualMode
                                    ? isActive
                                        ? `blur(0px)`
                                        : `blur(${blurAmount}px)`
                                    : isActive
                                        ? `blur(0px)`
                                        : `blur(${blurAmount}px)`,
                                transition: `filter ${animationDuration}s ease`,
                                outline: 'none',
                                userSelect: 'none'
                            } as React.CSSProperties
                        }
                        onMouseEnter={() => handleMouseEnter(index)}
                        onMouseLeave={handleMouseLeave}
                    >
                        <DecodingText text={currentText} />
                    </span>
                );
            })}

            <motion.div
                className="absolute top-0 left-0 pointer-events-none box-border border-0"
                animate={{
                    x: focusRect.x,
                    y: focusRect.y,
                    width: focusRect.width,
                    height: focusRect.height,
                    opacity: currentIndex >= 0 ? 1 : 0
                }}
                transition={{
                    duration: animationDuration
                }}
                style={
                    {
                        '--border-color': borderColor,
                        '--glow-color': glowColor
                    } as React.CSSProperties
                }
            >
                <span
                    className="absolute w-4 h-4 border-[3px] rounded-[3px] top-[-10px] left-[-10px] border-r-0 border-b-0"
                    style={{
                        borderColor: 'var(--border-color)',
                        filter: 'drop-shadow(0 0 4px var(--border-color))'
                    }}
                ></span>
                <span
                    className="absolute w-4 h-4 border-[3px] rounded-[3px] top-[-10px] right-[-10px] border-l-0 border-b-0"
                    style={{
                        borderColor: 'var(--border-color)',
                        filter: 'drop-shadow(0 0 4px var(--border-color))'
                    }}
                ></span>
                <span
                    className="absolute w-4 h-4 border-[3px] rounded-[3px] bottom-[-10px] left-[-10px] border-r-0 border-t-0"
                    style={{
                        borderColor: 'var(--border-color)',
                        filter: 'drop-shadow(0 0 4px var(--border-color))'
                    }}
                ></span>
                <span
                    className="absolute w-4 h-4 border-[3px] rounded-[3px] bottom-[-10px] right-[-10px] border-l-0 border-t-0"
                    style={{
                        borderColor: 'var(--border-color)',
                        filter: 'drop-shadow(0 0 4px var(--border-color))'
                    }}
                ></span>
            </motion.div>
        </div>
    );
};

export default TrueFocus;
