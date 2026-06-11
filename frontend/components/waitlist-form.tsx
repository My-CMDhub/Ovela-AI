"use client"

import React, { useState, useEffect } from "react"
import { motion } from "framer-motion"
import { waitlistClient, waitlistDatabases, WAITLIST_DATABASE_ID, WAITLIST_COLLECTION_ID } from "../lib/appwrite"
import { ID } from "appwrite"
import { syncPendingSubmissions, getPendingSubmissionsCount } from "../lib/sync-pending-submissions"
import { cn } from "@/lib/utils"

// Extend Window interface for Facebook Pixel
declare global {
    interface Window {
        fbq?: any
        _fbq?: any
    }
}

interface WaitlistFormProps {
    className?: string
    successMessage?: React.ReactNode
}

export function WaitlistForm({ className, successMessage }: WaitlistFormProps) {
    const [formData, setFormData] = useState({
        name: "",
        email: "",
        businessName: "",
        phone: "",
        businessSize: "",
    })
    const [status, setStatus] = useState<"idle" | "submitting" | "success" | "error" | "duplicate" | "offline">("idle")
    const [errorMessage, setErrorMessage] = useState("")

    // Verify Appwrite connection on mount
    useEffect(() => {
        const verifyConnection = async () => {
            try {
                if (!waitlistClient) {
                    console.warn("⚠️ Waitlist client not configured");
                    return;
                }
                await waitlistClient.ping();
                console.log("✅ Appwrite (Waitlist) connection established successfully!");

                // Auto-sync any pending submissions
                const pendingCount = getPendingSubmissionsCount();
                if (pendingCount > 0) {
                    console.log(`📋 Found ${pendingCount} pending submissions. Auto-syncing...`);
                    const result = await syncPendingSubmissions();
                    console.log(`📊 Sync complete: ${result.synced} synced, ${result.failed} failed`);

                    if (result.synced > 0) {
                        console.log(`✨ Successfully synced ${result.synced} waitlist application(s)!`);
                    }
                }
            } catch (error) {
                console.error("❌ Appwrite connection failed:", error);
                setErrorMessage("Database connection issue. Your submission will be saved locally and synced later.");
            }
        };
        verifyConnection();
    }, []);

    // Save to localStorage as backup
    const saveToLocalStorage = (data: typeof formData) => {
        try {
            const pending = JSON.parse(localStorage.getItem('ovela_pending_submissions') || '[]');
            pending.push({
                ...data,
                timestamp: new Date().toISOString(),
                synced: false
            });
            localStorage.setItem('ovela_pending_submissions', JSON.stringify(pending));
            console.log('📦 Submission saved to localStorage for later sync');
        } catch (err) {
            console.error('Failed to save to localStorage:', err);
        }
    };

    // Retry mechanism for failed submissions
    const retrySubmission = async (data: typeof formData, retries = 3): Promise<boolean> => {
        for (let attempt = 1; attempt <= retries; attempt++) {
            try {
                if (!waitlistDatabases || !WAITLIST_DATABASE_ID || !WAITLIST_COLLECTION_ID) {
                    throw new Error('Missing waitlist database configuration');
                }

                const randomClientId = Math.floor(Math.random() * 100000);

                await waitlistDatabases.createDocument(
                    WAITLIST_DATABASE_ID,
                    WAITLIST_COLLECTION_ID,
                    ID.unique(),
                    {
                        clientId: randomClientId,
                        Name: data.name,
                        email: data.email,
                        phoneNumber: data.phone,
                        StudioSize: data.businessSize,
                        StudioName: data.businessName,
                    }
                );

                console.log(`✅ Waitlist submission successful on attempt ${attempt}`);
                return true;
            } catch (error: any) {
                console.error(`❌ Attempt ${attempt} failed:`, error);

                // Don't retry on duplicate
                if (error?.code === 409) {
                    throw error;
                }

                // Wait before retry (exponential backoff)
                if (attempt < retries) {
                    await new Promise(resolve => setTimeout(resolve, 1000 * attempt));
                }
            }
        }
        return false;
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setStatus("submitting");
        setErrorMessage("");

        // Validate waitlist configuration
        if (!waitlistDatabases || !WAITLIST_DATABASE_ID || !WAITLIST_COLLECTION_ID) {
            console.error('Missing waitlist Appwrite configuration');
            setErrorMessage('Configuration error. Your submission has been saved locally.');
            saveToLocalStorage(formData);
            setStatus("offline");
            setFormData({ name: "", email: "", businessName: "", phone: "", businessSize: "" });
            return;
        }

        try {
            // Try to submit with retry logic
            const success = await retrySubmission(formData);

            if (success) {
                // Track Facebook Pixel Lead event (conversion)
                if (typeof window !== 'undefined' && window.fbq) {
                    window.fbq('track', 'Lead', {
                        content_name: 'Waitlist Application',
                        content_category: 'Lead Generation',
                        value: formData.businessSize,
                        currency: 'AUD'
                    });
                }

                setStatus("success");
                setFormData({ name: "", email: "", businessName: "", phone: "", businessSize: "" });
            } else {
                // All retries failed - save to localStorage
                saveToLocalStorage(formData);
                setStatus("offline");
                setErrorMessage("Couldn't connect to database. Your submission is saved and will sync automatically.");
                setFormData({ name: "", email: "", businessName: "", phone: "", businessSize: "" });
            }
        } catch (error: any) {
            console.error("Error submitting form:", error);

            // Handle duplicate entries
            if (error?.code === 409) {
                setStatus("duplicate");
                setFormData({ name: "", email: "", businessName: "", phone: "", businessSize: "" });
            } else {
                // Save to localStorage for any other error
                saveToLocalStorage(formData);
                setStatus("offline");
                setErrorMessage("Your application is saved! We'll process it once the connection is restored.");
                setFormData({ name: "", email: "", businessName: "", phone: "", businessSize: "" });
            }
        }
    };

    return (
        <motion.form
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6, ease: "easeOut", delay: 0.2 }}
            onSubmit={handleSubmit}
            className={cn(
                "space-y-6 bg-white/40 dark:bg-black/40 backdrop-blur-xl p-8 rounded-3xl border border-black/5 dark:border-white/10 shadow-2xl relative overflow-hidden transition-colors",
                className
            )}
        >
            {/* Shiny Bottom Reflection */}
            <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-3/4 h-px bg-gradient-to-r from-transparent via-zinc-300/50 dark:via-zinc-400/50 to-transparent blur-[1px]" />

            {status === "success" ? (
                <div className="text-center py-10">
                    <h3 className="text-2xl font-serif text-black dark:text-white mb-2">Welcome to the Waitlist!</h3>
                    <p className="text-zinc-600 dark:text-zinc-400">{successMessage || "We've received your application. Stay tuned."}</p>
                </div>
            ) : (
                <>
                    <div>
                        <input
                            type="text"
                            placeholder="Your name"
                            value={formData.name}
                            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                            className="w-full px-6 py-4 bg-black/5 dark:bg-white/5 border border-black/5 dark:border-white/10 rounded-xl text-sm text-black dark:text-white placeholder:text-zinc-500 focus:outline-none focus:ring-2 focus:ring-black/10 dark:focus:ring-white/20 transition-all"
                            required
                        />
                    </div>
                    <div>
                        <input
                            type="email"
                            placeholder="Email address"
                            value={formData.email}
                            onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                            className="w-full px-6 py-4 bg-black/5 dark:bg-white/5 border border-black/5 dark:border-white/10 rounded-xl text-sm text-black dark:text-white placeholder:text-zinc-500 focus:outline-none focus:ring-2 focus:ring-black/10 dark:focus:ring-white/20 transition-all"
                            required
                        />
                    </div>
                    <div>
                        <input
                            type="text"
                            placeholder="Business name"
                            value={formData.businessName}
                            onChange={(e) => setFormData({ ...formData, businessName: e.target.value })}
                            className="w-full px-6 py-4 bg-black/5 dark:bg-white/5 border border-black/5 dark:border-white/10 rounded-xl text-sm text-black dark:text-white placeholder:text-zinc-500 focus:outline-none focus:ring-2 focus:ring-black/10 dark:focus:ring-white/20 transition-all"
                            required
                        />
                    </div>
                    <div className="grid grid-cols-2 gap-6">
                        <input
                            type="tel"
                            placeholder="Phone number (optional)"
                            value={formData.phone}
                            onChange={(e) => {
                                // Only allow numbers, spaces, hyphens, parentheses, and plus sign
                                const value = e.target.value.replace(/[^\d\s\-\(\)\+]/g, '')
                                setFormData({ ...formData, phone: value })
                            }}
                            className="w-full px-6 py-4 bg-black/5 dark:bg-white/5 border border-black/5 dark:border-white/10 rounded-xl text-sm text-black dark:text-white placeholder:text-zinc-500 focus:outline-none focus:ring-2 focus:ring-black/10 dark:focus:ring-white/20 transition-all"
                        />
                        <div className="relative">
                            <select
                                value={formData.businessSize}
                                onChange={(e) => setFormData({ ...formData, businessSize: e.target.value })}
                                className="w-full px-6 py-4 bg-black/5 dark:bg-white/5 border border-black/5 dark:border-white/10 rounded-xl text-sm text-zinc-600 dark:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-black/10 dark:focus:ring-white/20 transition-all appearance-none"
                                required
                            >
                                <option value="" disabled>Team Size</option>
                                <option value="Solo">Just Me</option>
                                <option value="2-5 Staff">2-5 People</option>
                                <option value="6-10 Staff">6-10 People</option>
                                <option value="10+ Staff">10+ People</option>
                            </select>
                            <div className="absolute right-6 top-1/2 -translate-y-1/2 pointer-events-none text-zinc-500">
                                <svg width="10" height="6" viewBox="0 0 10 6" fill="none" xmlns="http://www.w3.org/2000/svg">
                                    <path d="M1 1L5 5L9 1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                                </svg>
                            </div>
                        </div>
                    </div>

                    <div>

                    </div>

                    <motion.button
                        whileHover={{ scale: 1.02 }}
                        whileTap={{ scale: 0.98 }}
                        type="submit"
                        disabled={status === "submitting"}
                        className="w-full py-4 bg-black text-white dark:bg-white dark:text-black rounded-full text-sm font-medium hover:bg-zinc-800 dark:hover:bg-zinc-200 transition-colors shadow-lg shadow-black/10 dark:shadow-white/10 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        {status === "submitting" ? "Joining..." : "Apply for Priority Access"}
                    </motion.button>

                    <p className="text-center text-xs text-zinc-500">
                        Limited spots available for this cohort. No credit card required.
                    </p>
                    {status === "error" && (
                        <p className="text-center text-xs text-red-500 dark:text-red-400">
                            {errorMessage || "Something went wrong. Please try again."}
                        </p>
                    )}
                    {status === "offline" && (
                        <div className="text-center text-xs space-y-1">
                            <p className="text-blue-600 dark:text-blue-400 font-medium">
                                ✓ Your application is saved!
                            </p>
                            <p className="text-zinc-500">
                                {errorMessage || "We'll process it once the connection is restored."}
                            </p>
                        </div>
                    )}
                    {status === "duplicate" && (
                        <p className="text-center text-xs text-amber-600 dark:text-amber-400">
                            You're already on the waitlist! We'll be in touch.
                        </p>
                    )}
                </>
            )}
        </motion.form>
    )
}
