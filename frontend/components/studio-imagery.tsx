"use client"

import { useRef, useState, useEffect } from "react"
import { motion, useScroll, useTransform, useMotionValueEvent, type MotionValue } from "framer-motion"
import { Search } from "lucide-react"
import Image from "next/image"

const FULL_TEXT = "nail salons with instant booking"

// Studio images for the reveal
const studioImages = [
  { src: "https://images.unsplash.com/photo-1600948836101-f9ffda59d250?w=800&q=80", alt: "Luxury nail salon", delay: 0 },
  { src: "https://images.unsplash.com/photo-1604654894610-df63bc536371?w=800&q=80", alt: "Modern beauty studio", delay: 0.1 },
  { src: "https://images.unsplash.com/photo-1610992015732-2449b76344bc?w=800&q=80", alt: "Elegant spa", delay: 0.05 },
  { src: "https://images.unsplash.com/photo-1522337660859-02fbefca4702?w=800&q=80", alt: "Professional nail art", delay: 0.15 },
  { src: "https://images.unsplash.com/photo-1540555700478-4be289fbecef?w=800&q=80", alt: "Upscale beauty parlor", delay: 0.08 },
  { src: "https://images.unsplash.com/photo-1519415387722-a1c3bbef716c?w=800&q=80", alt: "Chic nail studio", delay: 0.12 },
]

// Scenarios for the autopilot mode
// Scenarios for the autopilot mode with specific images
const SCENARIOS = [
  {
    text: "nail salons with instant booking",
    images: [
      { src: "https://images.unsplash.com/photo-1600948836101-f9ffda59d250?w=800&q=80", alt: "Luxury nail salon", delay: 0 },
      { src: "https://images.unsplash.com/photo-1519415387722-a1c3bbef716c?w=800&q=80", alt: "Chic nail studio", delay: 0.1 },
      { src: "https://images.unsplash.com/photo-1522337660859-02fbefca4702?w=800&q=80", alt: "Professional nail art", delay: 0.05 },
      { src: "https://images.unsplash.com/photo-1604654894610-df63bc536371?w=800&q=80", alt: "Modern beauty studio", delay: 0.15 },
      { src: "https://images.unsplash.com/photo-1540555700478-4be289fbecef?w=800&q=80", alt: "Upscale beauty parlor", delay: 0.08 },
      { src: "https://images.unsplash.com/photo-1610992015732-2449b76344bc?w=800&q=80", alt: "Elegant spa", delay: 0.12 },
    ]
  },
  {
    text: "24/7 AI Receptionist for your studio",
    images: [
      { src: "data:image/jpeg;base64,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", alt: "AI Receptionist", delay: 0 },
      { src: "https://images.unsplash.com/photo-1759143545924-beb85b33c0f1?w=900&auto=format&fit=crop&q=60&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxzZWFyY2h8Nnx8RGlnaXRhbCUyMGJvb2tpbmd8ZW58MHx8MHx8fDA%3D", alt: "Digital booking", delay: 0.1 },
      { src: "https://images.unsplash.com/photo-1560869713-7d0a29430803?w=900&auto=format&fit=crop&q=60&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxzZWFyY2h8Nnx8aGFpciUyMGN1dHxlbnwwfHwwfHx8MA%3D%3D", alt: "Smart studio", delay: 0.05 },
      { src: "https://images.unsplash.com/photo-1605497787907-66a1ca8a11bb?w=900&auto=format&fit=crop&q=60&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxwaG90by1yZWxhdGVkfDl8fHxlbnwwfHx8fHw%3D", alt: "Tech beauty", delay: 0.15 },
      { src: "https://images.unsplash.com/photo-1616394584738-fc6e612e71b9?w=900&auto=format&fit=crop&q=60&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxzZWFyY2h8NHx8ZmFjaWFsfGVufDB8fDB8fHww", alt: "Modern salon", delay: 0.08 },
      { src: "https://images.unsplash.com/photo-1702261952286-13005cc1a5cd?w=900&auto=format&fit=crop&q=60&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxzZWFyY2h8NHx8QmVhdXR5JTIwdGVjaHxlbnwwfHwwfHx8MA%3D%3D", alt: "Beauty tech", delay: 0.12 },
    ]
  },
  {
    text: "Zero missed calls, more bookings",
    images: [
      { src: "https://images.unsplash.com/photo-1629881544138-c45fc917eb81?w=900&auto=format&fit=crop&q=60&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxzZWFyY2h8Nnx8QnVzeSUyMHNhbG9ufGVufDB8fDB8fHww", alt: "Busy salon", delay: 0 },
      { src: "https://images.unsplash.com/photo-1484863137850-59afcfe05386?w=900&auto=format&fit=crop&q=60&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxzZWFyY2h8Nnx8SGFwcHklMjBjbGllbnRzfGVufDB8fDB8fHww", alt: "Happy clients", delay: 0.1 },
      { src: "https://images.unsplash.com/photo-1718815628185-2ff0f9332b32?w=900&auto=format&fit=crop&q=60&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxzZWFyY2h8Nnx8RnVsbCUyMHNjaGVkdWxlfGVufDB8fDB8fHww", alt: "Full schedule", delay: 0.05 },
      { src: "https://images.unsplash.com/photo-1556741533-6e6a62bd8b49?w=900&auto=format&fit=crop&q=60&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxzZWFyY2h8Mnx8UmVjZXB0aW9ufGVufDB8fDB8fHww", alt: "Reception", delay: 0.15 },
      { src: "https://images.unsplash.com/photo-1616394584738-fc6e612e71b9?w=900&auto=format&fit=crop&q=60&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxzZWFyY2h8NHx8ZmFjaWFsfGVufDB8fDB8fHww", alt: "Luxury interior", delay: 0.08 },
      { src: "https://images.unsplash.com/photo-1519415387722-a1c3bbef716c?w=900&auto=format&fit=crop&q=60&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxzZWFyY2h8Nnx8TmFpbC4gYW5kIGFydHxlbnwwfHwwfHx8MA%3D%3D", alt: "Nail art", delay: 0.12 },
    ]
  },
  {
    text: "Automated WhatsApp scheduling",
    images: [
      { src: "https://images.unsplash.com/photo-1642724978334-218b27d2c472?w=900&auto=format&fit=crop&q=60&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxzZWFyY2h8NXx8V2hhdHNBcHAlMjBib29raW5nfGVufDB8fDB8fHww", alt: "WhatsApp booking", delay: 0 },
      { src: "https://images.unsplash.com/photo-1758786977080-a5e60a3f843c?w=900&auto=format&fit=crop&q=60&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxzZWFyY2h8Mnx8TW9iaWxlJTIwc2NoZWR1bGluZ3xlbnwwfHwwfHx8MA%3D%3D", alt: "Mobile scheduling", delay: 0.1 },
      { src: "https://images.unsplash.com/photo-1506003094589-53954a26283f?w=900&auto=format&fit=crop&q=60&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxzZWFyY2h8Mzh8fGJvZHklMjBjYXJlfGVufDB8fDB8fHww", alt: "Digital assistant", delay: 0.15 },
      { src: "https://images.unsplash.com/photo-1519415387722-a1c3bbef716c?w=900&auto=format&fit=crop&q=60&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxzZWFyY2h8Nnx8TmFpbC4gYW5kIGFydHxlbnwwfHwwfHx8MA%3D%3D", alt: "Nail art", delay: 0.12 },
      { src: "https://images.unsplash.com/photo-1599387737838-660b75526801?w=900&auto=format&fit=crop&q=60&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxzZWFyY2h8MTV8fHNhbG9vbnxlbnwwfHwwfHx8MA%3D%3D", alt: "Modern studio", delay: 0.08 },
      { src: "https://images.unsplash.com/photo-1632345031435-8727f6897d53?w=900&auto=format&fit=crop&q=60&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxzZWFyY2h8Mnx8bmFpbCUyMGNhcmV8ZW58MHx8MHx8fDA%3D", alt: "Nail care", delay: 0.12 },
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

      const viewportHeight = window.innerHeight
      const scrollAdjustment = viewportHeight * 3.0
      window.scrollBy(0, -scrollAdjustment)
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
      className={`relative ${isAutopilot ? 'h-[100vh]' : 'h-[400vh]'}`}
      aria-label="Trusted by Modern Beauty Studios"
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
          <div className="absolute top-[42%] left-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-xl px-4 pointer-events-auto">
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
          Grow Your Salon Without <br className="hidden sm:block" />
          Growing Your Workload.
        </h2>
        <p className="mt-2 sm:mt-3 md:mt-3 text-sm md:text-base text-muted-foreground max-w-lg mx-auto">
          More bookings. Zero effort. The client retention engine you've been waiting for.
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
            sizes="(max-width: 768px) 50vw, 33vw"
          />
        </motion.div>
      </div>
    </motion.div>
  )
}
