"use client"

import { useRef, useState, useEffect } from "react"
import { motion, useScroll, useTransform, useMotionValueEvent, type MotionValue } from "framer-motion"
import { Search } from "lucide-react"
import Image from "next/image"

const FULL_TEXT = "Handle every booking call even when they overlap"

// Studio images for the reveal
const studioImages = [
  { src: "/studio_images/multiple-call.avif", alt: "Busy salon with calls ringing", delay: 0 },
  { src: "/studio_images/check-in.avif", alt: "Hotel reception with call log", delay: 0.1 },
  { src: "/studio_images/smile-business-owner.avif", alt: "Smiling business owner", delay: 0.05 },
  { src: "/studio_images/trade-man.avif", alt: "Tradesperson on the job", delay: 0.15 },
  { src: "/studio_images/agent-phone.avif", alt: "AI voice agent handling call", delay: 0.08 },
  { src: "/studio_images/phone.avif", alt: "Phone being answered", delay: 0.12 },
]

// Scenarios for the autopilot mode with specific images
const SCENARIOS = [
  {
    text: "Remove the call-capacity ceiling in your business",
    images: [
      { src: "/studio_images/multiple-call.avif", alt: "Busy salon with calls ringing", delay: 0 },
      { src: "/studio_images/check-in.avif", alt: "Hotel reception with call log", delay: 0.1 },
      { src: "/studio_images/trade-man.avif", alt: "Tradesperson on the job", delay: 0.05 },
      { src: "/studio_images/smile-business-owner.avif", alt: "Smiling business owner", delay: 0.15 },
      { src: "/studio_images/agent-phone.avif", alt: "AI voice agent handling call", delay: 0.08 },
      { src: "/studio_images/phone.avif", alt: "Phone being answered", delay: 0.12 },
    ]
  },
  {
    text: "Voice AI that captures demand 24/7",
    images: [
      { src: "/studio_images/agent-phone.avif", alt: "AI voice agent handling call", delay: 0 },
      { src: "/studio_images/phone.avif", alt: "Phone being answered", delay: 0.1 },
      { src: "/studio_images/check-in.avif", alt: "Hotel reception with call log", delay: 0.05 },
      { src: "/studio_images/smile-business-owner.avif", alt: "Smiling business owner", delay: 0.15 },
      { src: "/studio_images/trade-man.avif", alt: "Tradesperson on the job", delay: 0.08 },
      { src: "/studio_images/premium_photo-1664050114696-4ade533d4fe5.avif", alt: "Premium service business", delay: 0.12 },
    ]
  },
  {
    text: "Every inquiry answered. Every booking captured.",
    images: [
      { src: "/studio_images/smile-business-owner.avif", alt: "Smiling business owner", delay: 0 },
      { src: "/studio_images/check-in.avif", alt: "Hotel reception with call log", delay: 0.1 },
      { src: "/studio_images/multiple-call.avif", alt: "Busy salon with calls ringing", delay: 0.05 },
      { src: "/studio_images/agent-phone.avif", alt: "AI voice agent handling call", delay: 0.15 },
      { src: "/studio_images/trade-man.avif", alt: "Tradesperson on the job", delay: 0.08 },
      { src: "/studio_images/phone.avif", alt: "Phone being answered", delay: 0.12 },
    ]
  },
  {
    text: "Real-time bookings synced with your existing software",
    images: [
      { src: "/studio_images/phone.avif", alt: "Phone being answered", delay: 0 },
      { src: "/studio_images/check-in.avif", alt: "Hotel reception with call log", delay: 0.1 },
      { src: "/studio_images/agent-phone.avif", alt: "AI voice agent handling call", delay: 0.05 },
      { src: "/studio_images/premium_photo-1664050114696-4ade533d4fe5.avif", alt: "Premium service business", delay: 0.15 },
      { src: "/studio_images/smile-business-owner.avif", alt: "Smiling business owner", delay: 0.08 },
      { src: "/studio_images/trade-man.avif", alt: "Tradesperson on the job", delay: 0.12 },
    ]
  }
]

export function StudioImagery() {
  const containerRef = useRef<HTMLDivElement>(null)
  const [isAutopilot, setIsAutopilot] = useState(false)
  const [scenarioIndex, setScenarioIndex] = useState(0)

  // Track scroll progress within the 400vh container
  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ["start start", "end end"],
  })

  useMotionValueEvent(scrollYProgress, "change", (latest: number) => {
    if (latest > 0.99 && !isAutopilot) {
      setIsAutopilot(true)

      // Only apply scroll adjustment on desktop. Mobile browsers jump unpredictably.
      if (window.innerWidth >= 768) {
        const viewportHeight = window.innerHeight
        const scrollAdjustment = viewportHeight * 3.0
        window.scrollBy(0, -scrollAdjustment)
      }
    }
  })

  // ... (rest of code)

  // We need to change the render to NOT animate height, but switch it based on state.
  // And we need a layout effect to handle the scroll adjustment.


  // Phase 1: Entrance (0% - 15%)
  const searchBarScale = useTransform(scrollYProgress, [0, 0.15], [0.8, 1])
  const searchBarOpacity = useTransform(scrollYProgress, [0, 0.15], [0, 1])

  // Phase 2: Typing (15% - 60%) - Search bar LOCKED at center
  const typingProgress = useTransform(scrollYProgress, [0.15, 0.6], [0, 1])
  const progressBarWidth = useTransform(scrollYProgress, [0.15, 0.6], ["0%", "100%"])

  // Phase 3: Reveal (60% - 100%)
  const searchBarY = useTransform(scrollYProgress, [0.6, 0.75], ["0%", "-50%"])
  const baseImageY = useTransform(scrollYProgress, [0.6, 1], ["100vh", "0vh"])

  // Additional transforms (must be declared unconditionally)
  const hintOpacity = useTransform(scrollYProgress, [0.15, 0.2, 0.55, 0.6], [0, 1, 1, 0])
  const scrollIndicatorOpacity = useTransform(scrollYProgress, [0, 0.05], [1, 0])

  // Mobile image reveal transforms
  const mobileImageOpacity = useTransform(scrollYProgress, [0.6, 0.7], [0, 1])
  const mobileImageScale = useTransform(scrollYProgress, [0.6, 0.7], [0.9, 1])

  // Rotate images based on scenario
  const currentImages = isAutopilot
    ? SCENARIOS[scenarioIndex].images
    : studioImages

  return (
    <motion.section
      ref={containerRef}
      className={`relative ${isAutopilot ? 'md:h-[100vh] h-[400vh]' : 'h-[400vh]'}`}
      aria-label="Trusted by Modern Service Businesses"
    >
      <div className="sticky top-0 h-screen w-full overflow-hidden bg-gradient-to-b from-background via-background to-muted/20">

        {/* Background Pattern */}
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,_var(--tw-gradient-stops))] from-muted/30 via-transparent to-transparent opacity-50" />

        {/* 
           MOBILE LAYOUT: Flexbox Column
           Physically stacks elements so they CANNOT overlap.
           Visible only on mobile/tablet (md:hidden).
        */}
        <div className="absolute inset-0 z-20 flex flex-col h-full md:hidden pointer-events-none">

          {/* Top Images - Limited Height & Reveal Effect */}
          <motion.div
            style={{ opacity: isAutopilot ? 1 : mobileImageOpacity, scale: isAutopilot ? 1 : mobileImageScale }}
            className="w-full px-4 pt-20 flex-none pointer-events-auto h-[35vh] min-h-[200px] max-h-[300px]"
          >
            <div className="grid grid-cols-2 gap-3 h-full">
              {currentImages.slice(0, 2).map((image, index) => (
                <div key={`top-${index}-${isAutopilot}`} className="relative h-full w-full rounded-xl overflow-hidden shadow-lg bg-muted">
                  <Image
                    src={image.src}
                    alt={image.alt}
                    fill
                    className="object-cover"
                    sizes="(max-width: 768px) 50vw"
                  />
                </div>
              ))}
            </div>
          </motion.div>

          {/* Middle Content - Guaranteed Space */}
          <div className="flex-1 flex flex-col justify-center items-center w-full px-4 min-h-0 pointer-events-auto z-30">
            <SearchSection
              isAutopilot={isAutopilot}
              searchBarOpacity={searchBarOpacity}
              searchBarScale={searchBarScale}
              searchBarY={searchBarY}
              typingProgress={typingProgress}
              scenarioIndex={scenarioIndex}
              setScenarioIndex={setScenarioIndex}
              progressBarWidth={progressBarWidth}
              hintOpacity={hintOpacity}
            />
          </div>

          {/* Bottom Images - Limited Height & Reveal Effect */}
          <motion.div
            style={{ opacity: isAutopilot ? 1 : mobileImageOpacity, scale: isAutopilot ? 1 : mobileImageScale }}
            className="w-full px-4 pb-10 flex-none pointer-events-auto h-[35vh] min-h-[200px] max-h-[300px]"
          >
            <div className="grid grid-cols-2 gap-3 h-full">
              {currentImages.slice(2, 4).map((image, index) => (
                <div key={`bottom-${index}-${isAutopilot}`} className="relative h-full w-full rounded-xl overflow-hidden shadow-lg bg-muted">
                  <Image
                    src={image.src}
                    alt={image.alt}
                    fill
                    className="object-cover"
                    sizes="(max-width: 768px) 50vw"
                  />
                </div>
              ))}
            </div>
          </motion.div>
        </div>

        {/* 
           DESKTOP LAYOUT: Absolute Positioning
           Standard centering for stability on large screens.
           Visible only on desktop (hidden md:block).
        */}
        <div className="hidden md:block absolute inset-0 z-20 pointer-events-none">

          {/* Centered Content */}
          <div className="absolute top-[42%] left-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-2xl px-4 pointer-events-auto">
            <SearchSection
              isAutopilot={isAutopilot}
              searchBarOpacity={searchBarOpacity}
              searchBarScale={searchBarScale}
              searchBarY={searchBarY}
              typingProgress={typingProgress}
              scenarioIndex={scenarioIndex}
              setScenarioIndex={setScenarioIndex}
              progressBarWidth={progressBarWidth}
              hintOpacity={hintOpacity}
            />
          </div>

          {/* Bottom Image Grid - Full 6 images */}
          <motion.div
            style={{ y: isAutopilot ? "0vh" : baseImageY }}
            className="absolute inset-x-0 bottom-0 h-full pointer-events-none"
          >
            <div className="h-full flex items-end pb-10">
              <div className="mx-auto max-w-7xl px-4 w-full pointer-events-auto">
                <div className="grid grid-cols-6 gap-4">
                  {currentImages.map((image, index) => (
                    <ParallaxImage
                      key={`desktop-${index}-${isAutopilot}`}
                      src={image.src}
                      alt={image.alt}
                      scrollProgress={scrollYProgress}
                      parallaxOffset={image.delay}
                      index={index}
                      isAutopilot={isAutopilot}
                    />
                  ))}
                </div>
              </div>
            </div>
          </motion.div>
        </div>

        {/* Scroll Indicator */}
        <motion.div
          style={{
            opacity: isAutopilot ? 0 : scrollIndicatorOpacity,
          }}
          className="absolute bottom-8 left-1/2 -translate-x-1/2"
        >
          <div className="flex flex-col items-center gap-2">
            <span className="text-xs text-muted-foreground">Scroll to explore</span>
            <motion.div
              animate={{ y: [0, 8, 0] }}
              transition={{ duration: 1.5, repeat: Number.POSITIVE_INFINITY, ease: "easeInOut" }}
              className="h-6 w-4 rounded-full border-2 border-muted-foreground/50"
            >
              <motion.div
                animate={{ y: [0, 8, 0] }}
                transition={{ duration: 1.5, repeat: Number.POSITIVE_INFINITY, ease: "easeInOut" }}
                className="mx-auto mt-1 h-1.5 w-1 rounded-full bg-muted-foreground/50"
              />
            </motion.div>
          </div>
        </motion.div>
      </div>
    </motion.section>
  )
}

// Typewriter component
function TypewriterText({
  progress,
  text,
  isAutopilot,
  onCycle,
}: {
  progress: MotionValue<number>
  text: string
  isAutopilot: boolean
  onCycle?: () => void
}) {
  const [autoText, setAutoText] = useState("")

  // Manual scroll-based text
  const displayedText = useTransform(progress, (p: number) => {
    const charCount = Math.round(p * text.length)
    return text.slice(0, charCount)
  })

  useEffect(() => {
    if (!isAutopilot || !onCycle) return

    let timeout: NodeJS.Timeout
    let isDeleting = false
    let charIndex = 0 // Start from 0 for new text

    // Initial delay before typing starts
    const startDelay = 500

    const typeLoop = () => {
      const current = text.substring(0, charIndex)
      setAutoText(current)

      let typeSpeed = 50 + Math.random() * 50 // Random typing speed for realism

      if (isDeleting) {
        typeSpeed /= 2 // Delete faster
      }

      if (!isDeleting && charIndex === text.length) {
        // Finished typing
        typeSpeed = 2000 // Pause at end to read
        isDeleting = true
      } else if (isDeleting && charIndex === 0) {
        // Finished deleting
        isDeleting = false
        onCycle() // Trigger next scenario
        return // Stop this loop, effect will re-run with new text
      }

      if (isDeleting) {
        charIndex--
      } else {
        charIndex++
      }

      timeout = setTimeout(typeLoop, typeSpeed)
    }

    // Start the loop
    timeout = setTimeout(typeLoop, startDelay)

    return () => clearTimeout(timeout)
  }, [isAutopilot, text, onCycle]) // Re-run when text changes (new scenario)

  return (
    <div className="relative min-h-[1.5rem]">
      <motion.span className="text-lg font-medium text-foreground sm:text-xl">
        <TextDisplay
          key={isAutopilot ? "auto" : "manual"}
          text={isAutopilot ? autoText : displayedText}
        />
      </motion.span>
    </div>
  )
}

// Text display component
function TextDisplay({
  text,
}: {
  text: MotionValue<string> | string
}) {
  return (
    <motion.span>
      <motion.span>{text}</motion.span>
      <motion.span
        animate={{ opacity: [1, 0] }}
        transition={{ duration: 0.5, repeat: Number.POSITIVE_INFINITY, repeatType: "reverse" }}
        className="ml-0.5 inline-block h-5 w-0.5 bg-primary align-middle"
      />
    </motion.span>
  )
}

// Search Section Component to avoid duplication
function SearchSection({
  isAutopilot,
  searchBarOpacity,
  searchBarScale,
  searchBarY,
  typingProgress,
  scenarioIndex,
  setScenarioIndex,
  progressBarWidth,
  hintOpacity,
}: {
  isAutopilot: boolean
  searchBarOpacity: MotionValue<number>
  searchBarScale: MotionValue<number>
  searchBarY: MotionValue<string>
  typingProgress: MotionValue<number>
  scenarioIndex: number
  setScenarioIndex: React.Dispatch<React.SetStateAction<number>>
  progressBarWidth: MotionValue<string>
  hintOpacity: MotionValue<number>
}) {
  return (
    <div className="w-full">
      {/* Section Heading - Fades in/out */}
      <motion.div
        style={{ opacity: isAutopilot ? 1 : searchBarOpacity }}
        className="mt-10 md:mt-0 mb-4 sm:mb-6 md:mb-8 text-center"
      >
        <h2 className="text-balance text-2xl sm:text-3xl font-semibold tracking-tight text-foreground md:text-4xl lg:text-5xl">
          Grow bookings <br className="hidden sm:block" />
          without increasing reception workload.
        </h2>
        <p className="mt-2 sm:mt-3 md:mt-3 text-sm md:text-base text-muted-foreground max-w-lg mx-auto">
          Every call answered. Every booking captured. The AI receptionist your business deserves.
        </p>
      </motion.div>

      {/* Search Bar - The Hero */}
      <motion.div
        key={isAutopilot ? "auto" : "manual"}
        style={{
          scale: isAutopilot ? 1 : searchBarScale,
          opacity: isAutopilot ? 1 : searchBarOpacity,
          y: isAutopilot ? "-50%" : searchBarY,
        }}
        className="w-full"
      >
        <div className="relative overflow-hidden rounded-xl sm:rounded-2xl border border-border bg-card shadow-2xl shadow-black/10 mt-18 sm:mt-16 md:mt-18">
          <div className="flex items-center gap-2 sm:gap-3 p-3 sm:p-4 md:p-5">
            <div className="flex h-8 w-8 sm:h-10 sm:w-10 shrink-0 items-center justify-center rounded-lg sm:rounded-xl bg-primary/10">
              <Search className="h-4 w-4 sm:h-5 sm:w-5 text-primary" />
            </div>
            <div className="flex-1 min-w-0">
              <TypewriterText
                progress={typingProgress}
                text={isAutopilot ? SCENARIOS[scenarioIndex].text : FULL_TEXT}
                isAutopilot={isAutopilot}
                onCycle={() => setScenarioIndex(prev => (prev + 1) % SCENARIOS.length)}
              />
            </div>
          </div>

          {/* Progress Bar */}
          <div className="h-0.5 sm:h-1 w-full bg-muted">
            <motion.div
              style={{ width: isAutopilot ? "100%" : progressBarWidth }}
              className="h-full bg-gradient-to-r from-primary via-primary to-primary/80"
            />
          </div>
        </div>

        {/* Hint Text */}
        <motion.p
          style={{
            opacity: isAutopilot ? 0 : hintOpacity,
            fontSize: 'clamp(0.625rem, 2.5vw, 0.875rem)'
          }}
          className="mt-2 sm:mt-3 md:mt-4 text-center text-muted-foreground"
        >
          Scroll to search...
        </motion.p>
      </motion.div>
    </div>
  )
}

// Parallax image component
function ParallaxImage({
  src,
  alt,
  scrollProgress,
  parallaxOffset,
  index,
  isAutopilot,
}: {
  src: string
  alt: string
  scrollProgress: MotionValue<number>
  parallaxOffset: number
  index: number
  isAutopilot: boolean
}) {
  const imageY = useTransform(scrollProgress, [0.6 + parallaxOffset, 1], ["20%", "0%"])
  const imageOpacity = useTransform(scrollProgress, [0.6 + parallaxOffset, 0.7 + parallaxOffset], [0, 1])
  const imageScale = useTransform(scrollProgress, [0.6 + parallaxOffset, 0.85], [0.9, 1])

  // Autopilot highlight effect
  const [isHighlighted, setIsHighlighted] = useState(false)

  useEffect(() => {
    if (!isAutopilot) return

    // Random highlight cycle
    const interval = setInterval(() => {
      setIsHighlighted(Math.random() > 0.7)
    }, 2000 + (index * 500))

    return () => clearInterval(interval)
  }, [isAutopilot, index])

  return (
    <motion.div
      style={{
        y: isAutopilot ? "0%" : imageY,
        opacity: isAutopilot ? 1 : imageOpacity,
        scale: isAutopilot ? (isHighlighted ? 1.05 : 1) : imageScale,
      }}
      animate={isAutopilot ? {
        scale: isHighlighted ? 1.05 : 1,
        filter: isHighlighted ? "brightness(1.1)" : "brightness(1)",
      } : {}}
      transition={{ duration: 0.5 }}
      className="overflow-hidden rounded-xl shadow-lg bg-muted"
    >
      <div className="aspect-[3/4] w-full relative">
        <motion.div
          key={src} // Animate when src changes
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.5 }}
          className="absolute inset-0"
        >
          <Image
            src={src || "/placeholder.svg"}
            alt={alt}
            fill
            className="object-cover transition-transform duration-500 hover:scale-105"
            sizes="(max-width: 768px) 50vw, 17vw"
          />
        </motion.div>
      </div>
    </motion.div>
  )
}
