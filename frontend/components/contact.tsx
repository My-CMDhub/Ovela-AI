"use client"

import React, { useState, useEffect, useRef } from "react"

import { motion } from "framer-motion"


import { waitlistClient, waitlistDatabases, WAITLIST_DATABASE_ID, WAITLIST_COLLECTION_ID } from "../lib/appwrite"
import { ID } from "appwrite"
import { syncPendingSubmissions, getPendingSubmissionsCount } from "../lib/sync-pending-submissions"

// Extend Window interface for Facebook Pixel
declare global {
  interface Window {
    fbq?: any
    _fbq?: any
  }
}

export function Contact() {
  const [formData, setFormData] = useState({
    name: "",
    email: "",
    studioName: "",
    phone: "",
    studioSize: "",
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
            StudioSize: data.studioSize,
            StudioName: data.studioName,
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
      setFormData({ name: "", email: "", studioName: "", phone: "", studioSize: "" });
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
            value: formData.studioSize,
            currency: 'AUD'
          });
        }

        setStatus("success");
        setFormData({ name: "", email: "", studioName: "", phone: "", studioSize: "" });
      } else {
        // All retries failed - save to localStorage
        saveToLocalStorage(formData);
        setStatus("offline");
        setErrorMessage("Couldn't connect to database. Your submission is saved and will sync automatically.");
        setFormData({ name: "", email: "", studioName: "", phone: "", studioSize: "" });
      }
    } catch (error: any) {
      console.error("Error submitting form:", error);

      // Handle duplicate entries
      if (error?.code === 409) {
        setStatus("duplicate");
        setFormData({ name: "", email: "", studioName: "", phone: "", studioSize: "" });
      } else {
        // Save to localStorage for any other error
        saveToLocalStorage(formData);
        setStatus("offline");
        setErrorMessage("Your application is saved! We'll process it once the connection is restored.");
        setFormData({ name: "", email: "", studioName: "", phone: "", studioSize: "" });
      }
    }
  };

  const video1Ref = useRef<HTMLVideoElement>(null)
  const video2Ref = useRef<HTMLVideoElement>(null)
  const sectionRef = useRef<HTMLElement>(null)
  const [activeVideo, setActiveVideo] = useState<1 | 2>(1)
  const [isTransitioning, setIsTransitioning] = useState(false)
  const [hasStarted, setHasStarted] = useState(false)

  // Use Intersection Observer to trigger video when section comes into view
  // This fixes Safari autoplay issues when navigating via scroll vs direct navigation
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting && !hasStarted) {
            setHasStarted(true)
            const playVideo = async () => {
              if (video1Ref.current) {
                try {
                  // Safari sometimes needs the video to be loaded first
                  video1Ref.current.load()
                  // Small delay to ensure video is ready
                  await new Promise(resolve => setTimeout(resolve, 100))
                  await video1Ref.current.play()
                } catch (err) {
                  console.log('Video autoplay prevented on first attempt, retrying...', err)
                  // Retry after a short delay (Safari workaround)
                  setTimeout(async () => {
                    try {
                      if (video1Ref.current) {
                        video1Ref.current.load()
                        await video1Ref.current.play()
                      }
                    } catch (retryErr) {
                      console.log('Video autoplay still prevented:', retryErr)
                      // Last resort: try on next user interaction
                      const playOnInteraction = async () => {
                        try {
                          if (video1Ref.current) {
                            await video1Ref.current.play()
                            document.removeEventListener('click', playOnInteraction)
                            document.removeEventListener('touchstart', playOnInteraction)
                          }
                        } catch (e) {
                          console.log('Video play failed even on interaction:', e)
                        }
                      }
                      document.addEventListener('click', playOnInteraction, { once: true })
                      document.addEventListener('touchstart', playOnInteraction, { once: true })
                    }
                  }, 300)
                }
              }
            }
            playVideo()
          }
        })
      },
      {
        threshold: 0.25, // Trigger when 25% of the section is visible
        rootMargin: '0px 0px -100px 0px' // Start slightly before it comes fully into view
      }
    )

    if (sectionRef.current) {
      observer.observe(sectionRef.current)
    }

    return () => {
      if (sectionRef.current) {
        observer.unobserve(sectionRef.current)
      }
    }
  }, [hasStarted])

  const handleTimeUpdate = (e: React.SyntheticEvent<HTMLVideoElement>) => {
    const video = e.currentTarget
    const duration = video.duration
    const currentTime = video.currentTime
    const transitionTime = 1.5 // Seconds before end to start transition

    if (duration > 0 && duration - currentTime <= transitionTime && !isTransitioning) {
      setIsTransitioning(true)
      const nextVideo = activeVideo === 1 ? video2Ref.current : video1Ref.current

      if (nextVideo) {
        nextVideo.currentTime = 0
        nextVideo.play()
        setActiveVideo(activeVideo === 1 ? 2 : 1)

        // Reset transition flag after transition completes
        setTimeout(() => {
          setIsTransitioning(false)
          video.pause()
          video.currentTime = 0
        }, transitionTime * 1000)
      }
    }
  }

  return (
    <section ref={sectionRef} id="contact" className="relative overflow-hidden min-h-screen bg-white dark:bg-black transition-colors duration-300">
      {/* Video Background - Dual Video Crossfade for Perfect Loop */}
      <div className="absolute inset-0 z-0">
        <video
          ref={video1Ref}
          autoPlay
          muted
          playsInline
          webkit-playsinline="true"
          x5-playsinline="true"
          preload="metadata"
          onTimeUpdate={activeVideo === 1 ? handleTimeUpdate : undefined}
          className={`absolute inset-0 w-full h-full object-cover invert dark:invert-0 transition-opacity duration-[1500ms] ${activeVideo === 1 ? 'opacity-50 z-10' : 'opacity-0 z-0'}`}
        >
          <source src="/wave-bg.mov" type="video/mp4" />
          <source src="/wave-bg.mov" type="video/quicktime" />
        </video>
        <video
          ref={video2Ref}
          muted
          playsInline
          webkit-playsinline="true"
          x5-playsinline="true"
          preload="metadata"
          onTimeUpdate={activeVideo === 2 ? handleTimeUpdate : undefined}
          className={`absolute inset-0 w-full h-full object-cover invert dark:invert-0 transition-opacity duration-[1500ms] ${activeVideo === 2 ? 'opacity-50 z-10' : 'opacity-0 z-0'}`}
        >
          <source src="/wave-bg.mov" type="video/mp4" />
          <source src="/wave-bg.mov" type="video/quicktime" />
        </video>

        {/* Gradient Overlay for better text readability */}
        <div className="absolute inset-0 z-20 bg-gradient-to-t from-white via-white/50 to-transparent dark:from-black dark:via-black/50" />
      </div>

      <div className="relative z-10 w-full max-w-xl mx-auto px-6 pt-32 pb-40">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, ease: "easeOut" }}
          className="text-center mb-12"
        >
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-black/5 border border-black/10 text-black dark:bg-white/5 dark:border-white/10 dark:text-white text-xs font-medium tracking-wider uppercase mb-6 backdrop-blur-md transition-colors">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-black dark:bg-white opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-black dark:bg-white"></span>
            </span>
            Applications Open
          </div>
          <h2 className="font-serif text-4xl md:text-5xl tracking-tight mb-4 text-black dark:text-white transition-colors">Join the Exclusive Waitlist</h2>
          <p className="text-zinc-600 dark:text-zinc-400 text-lg transition-colors">Secure your spot for the next intake. Priority access for early applicants.</p>
        </motion.div>

        <div className="relative">
          {/* Soothing Scatter Glow Effect - Bottom Edge */}
          <div className="absolute -bottom-12 left-0 right-0 h-64 -z-10 pointer-events-none">
            {/* Main visible glow at bottom */}
            <motion.div
              className="absolute bottom-0 left-1/2 -translate-x-1/2 w-full h-48 bg-gradient-to-t from-zinc-200/60 via-zinc-300/20 to-transparent dark:from-zinc-400/60 dark:via-zinc-500/20 blur-[40px]"
              animate={{ opacity: [0.6, 0.9, 0.6] }}
              transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
            />

            {/* Scattered glow particles */}
            <motion.div
              className="absolute bottom-8 left-[15%] w-32 h-32 bg-zinc-200/40 dark:bg-white/40 blur-[30px] rounded-full"
              animate={{ opacity: [0.4, 0.7, 0.4], scale: [1, 1.2, 1] }}
              transition={{ duration: 5, repeat: Infinity, ease: "easeInOut" }}
            />

            <motion.div
              className="absolute bottom-12 right-[15%] w-40 h-40 bg-zinc-300/40 dark:bg-zinc-300/40 blur-[35px] rounded-full"
              animate={{ opacity: [0.4, 0.7, 0.4], scale: [1, 1.15, 1] }}
              transition={{ duration: 6, repeat: Infinity, ease: "easeInOut", delay: 0.8 }}
            />

            <motion.div
              className="absolute bottom-6 left-1/2 -translate-x-1/2 w-48 h-24 bg-zinc-200/30 dark:bg-white/30 blur-[25px] rounded-full"
              animate={{ opacity: [0.5, 0.8, 0.5] }}
              transition={{ duration: 3.5, repeat: Infinity, ease: "easeInOut", delay: 0.3 }}
            />

            {/* Shiny accent dots */}
            <motion.div
              className="absolute bottom-16 left-[30%] w-2 h-2 bg-white/90 blur-sm rounded-full"
              animate={{ opacity: [0, 1, 0], y: [0, -10, 0] }}
              transition={{ duration: 3, repeat: Infinity, ease: "easeInOut", delay: 0.5 }}
            />
            <motion.div
              className="absolute bottom-20 right-[30%] w-2 h-2 bg-white/80 blur-sm rounded-full"
              animate={{ opacity: [0, 1, 0], y: [0, -12, 0] }}
              transition={{ duration: 3.5, repeat: Infinity, ease: "easeInOut", delay: 1.5 }}
            />
          </div>

          <motion.form
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6, ease: "easeOut", delay: 0.2 }}
            onSubmit={handleSubmit}
            className="space-y-6 bg-white/40 dark:bg-black/40 backdrop-blur-xl p-8 rounded-3xl border border-black/5 dark:border-white/10 shadow-2xl relative overflow-hidden transition-colors"
          >
            {/* Shiny Bottom Reflection */}
            <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-3/4 h-px bg-gradient-to-r from-transparent via-zinc-300/50 dark:via-zinc-400/50 to-transparent blur-[1px]" />

            {status === "success" ? (
              <div className="text-center py-10">
                <h3 className="text-2xl font-serif text-black dark:text-white mb-2">Welcome to the Waitlist!</h3>
                <p className="text-zinc-600 dark:text-zinc-400">We've received your application. Stay tuned.</p>
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
                    placeholder="Studio name"
                    value={formData.studioName}
                    onChange={(e) => setFormData({ ...formData, studioName: e.target.value })}
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
                      value={formData.studioSize}
                      onChange={(e) => setFormData({ ...formData, studioSize: e.target.value })}
                      className="w-full px-6 py-4 bg-black/5 dark:bg-white/5 border border-black/5 dark:border-white/10 rounded-xl text-sm text-zinc-600 dark:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-black/10 dark:focus:ring-white/20 transition-all appearance-none"
                      required
                    >
                      <option value="" disabled>Studio Size</option>
                      <option value="Solo Studio">Solo Studio</option>
                      <option value="2-5 Staff">2-5 Staff</option>
                      <option value="6-10 Staff">6-10 Staff</option>
                      <option value="10+ Staff">10+ Staff</option>
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
        </div>
      </div>
    </section>
  )
}