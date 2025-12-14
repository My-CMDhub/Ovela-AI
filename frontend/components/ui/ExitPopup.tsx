"use client";

import { motion, AnimatePresence } from "framer-motion";
import { useState, useEffect } from "react";
import { X, ArrowRight, Zap, CheckCircle2 } from "lucide-react";
import { client, databases } from "@/lib/appwrite";
import { ID } from "appwrite";

export function ExitPopup() {
    const [isVisible, setIsVisible] = useState(false);
    const [hasSeenPopup, setHasSeenPopup] = useState(false);
    const [email, setEmail] = useState("");
    const [status, setStatus] = useState<"idle" | "submitting" | "success" | "error" | "duplicate">("idle");

    // Configuration
    const TIME_DELAY = 12000;
    const SHOW_ONCE_KEY = "ovela_popup_seen";

    useEffect(() => {
        // Check if already seen/subscribed
        const seen = localStorage.getItem(SHOW_ONCE_KEY);
        if (seen) {
            setHasSeenPopup(true);
            return;
        }

        // Timer Trigger
        const timer = setTimeout(() => {
            if (!hasSeenPopup) openPopup();
        }, TIME_DELAY);

        // Exit Intent Trigger
        const handleMouseLeave = (e: MouseEvent) => {
            if (e.clientY <= 0 && !hasSeenPopup) {
                openPopup();
            }
        };

        document.addEventListener("mouseleave", handleMouseLeave);

        return () => {
            clearTimeout(timer);
            document.removeEventListener("mouseleave", handleMouseLeave);
        };
    }, [hasSeenPopup]);

    const openPopup = () => {
        const seen = localStorage.getItem(SHOW_ONCE_KEY);
        if (!seen) {
            setIsVisible(true);
            setHasSeenPopup(true);
            localStorage.setItem(SHOW_ONCE_KEY, "true");
        }
    };

    const handleClose = () => {
        setIsVisible(false);
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!email) return;

        setStatus("submitting");

        try {
            // Direct submission
            await databases.createDocument(
                process.env.NEXT_PUBLIC_APPWRITE_DATABASE_ID!,
                process.env.NEXT_PUBLIC_APPWRITE_COLLECTION_ID!,
                ID.unique(),
                {
                    clientId: Math.floor(Math.random() * 100000),
                    Name: "Guest", // Default for popup
                    email,
                    phoneNumber: "N/A",
                    StudioSize: "N/A",
                    StudioName: "Popup Capture", // Tag the source
                }
            );

            setStatus("success");

            // Auto close after success
            setTimeout(() => {
                setIsVisible(false);
            }, 3000);

        } catch (error: any) {
            if (error.code === 409) {
                setStatus("duplicate");
                return;
            }
            console.error("Popup submission error:", error);
            setStatus("error");
        }
    };

    return (
        <AnimatePresence>
            {isVisible && (
                <>
                    {/* Backdrop */}
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        onClick={handleClose}
                        className="fixed inset-0 bg-black/40 backdrop-blur-sm z-[100]"
                    />

                    {/* Popup Card */}
                    <motion.div
                        initial={{ opacity: 0, scale: 0.95, y: 20 }}
                        animate={{ opacity: 1, scale: 1, y: 0 }}
                        exit={{ opacity: 0, scale: 0.95, y: 20 }}
                        className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-[101] w-full max-w-md p-4"
                    >
                        <div className="relative overflow-hidden rounded-2xl bg-white text-black shadow-2xl ring-1 ring-black/5">

                            <button
                                onClick={handleClose}
                                className="absolute top-4 right-4 p-2 text-zinc-400 hover:text-black transition-colors z-10"
                            >
                                <X size={20} />
                            </button>

                            <div className="p-8">
                                <motion.div
                                    initial={{ scale: 0.8, opacity: 0 }}
                                    animate={{ scale: 1, opacity: 1 }}
                                    transition={{ delay: 0.1 }}
                                    className="w-12 h-12 bg-black text-white rounded-full flex items-center justify-center mb-6"
                                >
                                    <Zap className="w-6 h-6" />
                                </motion.div>

                                <h3 className="text-2xl font-serif font-bold text-black mb-2">
                                    Wait! Don't run your studio manually.
                                </h3>
                                <p className="text-zinc-600 mb-8 leading-relaxed text-sm">
                                    Get our free <strong>Automation Blueprint</strong>. Join 500+ studio owners saving 20h/week with these 3 simple workflows.
                                </p>

                                {status === "success" ? (
                                    <motion.div
                                        initial={{ opacity: 0, y: 10 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        className="bg-green-50 text-green-700 p-4 rounded-xl flex items-center gap-3"
                                    >
                                        <CheckCircle2 size={20} />
                                        <p className="font-medium">Blueprint sent to your inbox!</p>
                                    </motion.div>
                                ) : (
                                    <form onSubmit={handleSubmit} className="space-y-4">
                                        <div className="relative">
                                            <input
                                                type="email"
                                                placeholder="Enter your email"
                                                value={email}
                                                onChange={(e) => setEmail(e.target.value)}
                                                required
                                                className="w-full bg-zinc-50 border border-zinc-200 rounded-xl px-4 py-3 text-black placeholder:text-zinc-400 focus:outline-none focus:border-black focus:ring-1 focus:ring-black transition-all"
                                            />
                                        </div>

                                        <button
                                            type="submit"
                                            disabled={status === "submitting"}
                                            className="w-full bg-black text-white font-medium py-3 rounded-xl hover:bg-zinc-800 transition-colors flex items-center justify-center gap-2 group disabled:opacity-70 disabled:cursor-not-allowed"
                                        >
                                            {status === "submitting" ? (
                                                <span className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                            ) : (
                                                <>
                                                    Send Me The Blueprint
                                                    <ArrowRight size={16} className="group-hover:translate-x-1 transition-transform" />
                                                </>
                                            )}
                                        </button>

                                        {status === "duplicate" && (
                                            <p className="text-amber-600 text-xs mt-2 text-center">You're already on the list!</p>
                                        )}
                                        {status === "error" && (
                                            <p className="text-red-500 text-xs mt-2 text-center">Something went wrong. Please try again.</p>
                                        )}
                                    </form>
                                )}

                                <p className="mt-6 text-[10px] text-zinc-400 text-center">
                                    No spam. Unsubscribe anytime.
                                </p>
                            </div>
                        </div>
                    </motion.div>
                </>
            )}
        </AnimatePresence>
    );
}
