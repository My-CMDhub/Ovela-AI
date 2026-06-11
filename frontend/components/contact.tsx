"use client"

import React, { useState, useEffect, useRef } from "react"

import { motion } from "framer-motion"


import { WaitlistForm } from "./waitlist-form"

export function Contact() {

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
        // Wrap play() in async handler to catch autoplay rejection
        const playNext = async () => {
          try {
            await nextVideo.play()
          } catch (err) {
            console.log('Video crossfade play prevented:', err)
          }
        }
        playNext()
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
          <p className="text-zinc-600 dark:text-zinc-400 text-lg transition-colors text-balance">
            Secure your spot for the next intake. Priority access for early applicants.
          </p>
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

          <WaitlistForm />
        </div>
      </div>
    </section>
  )
}