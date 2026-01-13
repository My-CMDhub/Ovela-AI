import { motion, AnimatePresence, LayoutGroup } from "framer-motion"
import { Plus } from "lucide-react"
import { useState } from "react"

interface PainPoint {
    label: string
    problem: string
}

export function FrictionList({ items }: { items: PainPoint[] }) {
    const [activeIndex, setActiveIndex] = useState<number | null>(0)

    return (
        <LayoutGroup>
            {/* Min-height prevents drastic layout jumps when collapsing/expanding */}
            <div className="w-full max-w-3xl space-y-4 min-h-[420px]">
                {items.map((item, idx) => (
                    <motion.button
                        layout
                        key={idx}
                        onMouseEnter={() => setActiveIndex(idx)}
                        onClick={() => setActiveIndex(idx)}
                        initial={false}
                        animate={{
                            backgroundColor: activeIndex === idx ? "rgba(var(--primary-rgb), 0.03)" : "rgba(0,0,0,0)",
                            borderColor: activeIndex === idx ? "rgba(var(--primary-rgb), 0.2)" : "rgba(var(--border-rgb), 0.4)"
                        }}
                        className="flex flex-col w-full text-left border-b border-border/40 overflow-hidden cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-primary/20 rounded-md"
                        transition={{ duration: 0.3, ease: "easeInOut" }}
                    >
                        <motion.div layout="position" className="flex items-center justify-between py-4 px-2 select-none w-full">
                            <div className="flex items-center gap-4">
                                <span className={`font-mono text-sm transition-colors duration-300 ${activeIndex === idx ? "text-primary" : "text-muted-foreground/50"}`}>
                                    0{idx + 1}
                                </span>
                                <h3 className={`text-xl md:text-2xl font-medium tracking-tight transition-colors duration-300 ${activeIndex === idx ? "text-foreground" : "text-muted-foreground"}`}>
                                    {item.label}
                                </h3>
                            </div>
                            <motion.div
                                layout="position"
                                animate={{
                                    rotate: activeIndex === idx ? 45 : 0,
                                    opacity: activeIndex === idx ? 1 : 0.5
                                }}
                                className={`p-2 rounded-full ${activeIndex === idx ? "text-primary bg-primary/10" : "text-muted-foreground"}`}
                            >
                                <Plus className="w-5 h-5" />
                            </motion.div>
                        </motion.div>

                        <AnimatePresence mode="popLayout">
                            {activeIndex === idx && (
                                <motion.div
                                    initial={{ height: 0, opacity: 0 }}
                                    animate={{ height: "auto", opacity: 1 }}
                                    exit={{ height: 0, opacity: 0 }}
                                    transition={{ duration: 0.3, ease: "circOut" }}
                                >
                                    <div className="pl-12 pr-4 pb-6">
                                        <p className="text-lg text-muted-foreground leading-relaxed border-l-2 border-primary/20 pl-6">
                                            {item.problem}
                                        </p>
                                    </div>
                                </motion.div>
                            )}
                        </AnimatePresence>
                    </motion.button>
                ))}
            </div>
        </LayoutGroup>
    )
}
