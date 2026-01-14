"use client"

import { useState, useEffect } from "react"
import dynamic from "next/dynamic"
import { AnimatePresence, motion } from "framer-motion"
import { Header } from "@/components/header"
import { Hero } from "@/components/hero"
import { Preloader } from "@/components/preloader"
import { ExitPopup } from "@/components/ui/ExitPopup"

// Lazy load heavy components to improve initial load time
const StudioImagery = dynamic(() => import("@/components/studio-imagery").then(mod => ({ default: mod.StudioImagery })), {
  loading: () => <div className="min-h-screen" />,
  ssr: false,
})

const ProblemSolution = dynamic(() => import("@/components/problem-solution").then(mod => ({ default: mod.ProblemSolution })), {
  loading: () => <div className="min-h-screen" />,
  ssr: false,
})

const Features = dynamic(() => import("@/components/features").then(mod => ({ default: mod.Features })), {
  loading: () => <div className="min-h-[600px]" />,
  ssr: false,
})

const LivePreview = dynamic(() => import("@/components/live-preview").then(mod => ({ default: mod.LivePreview })), {
  loading: () => <div className="min-h-screen" />,
  ssr: false,
})

const Testimonials = dynamic(() => import("@/components/testimonials").then(mod => ({ default: mod.Testimonials })), {
  loading: () => <div className="min-h-[400px]" />,
  ssr: false,
})

const Pricing = dynamic(() => import("@/components/pricing").then(mod => ({ default: mod.Pricing })), {
  loading: () => <div className="min-h-screen" />,
  ssr: false,
})

const Contact = dynamic(() => import("@/components/contact").then(mod => ({ default: mod.Contact })), {
  loading: () => <div className="min-h-screen" />,
  ssr: false,
})

const Footer = dynamic(() => import("@/components/footer").then(mod => ({ default: mod.Footer })), {
  loading: () => <div className="min-h-[200px]" />,
  ssr: false,
})

export default function Home() {
  const [isLoading, setIsLoading] = useState(true)

  // Handle hash navigation after loading completes
  useEffect(() => {
    if (!isLoading) {
      // Prevent browser from trying to restore scroll position automatically which fights our scroll
      if ('scrollRestoration' in window.history) {
        window.history.scrollRestoration = 'manual'
      }

      const hash = window.location.hash
      if (hash) {
        const id = hash.replace('#', '')

        // Poll for the element being available in the DOM
        const checkForElement = setInterval(() => {
          const element = document.getElementById(id)
          if (element) {
            clearInterval(checkForElement)
            // Small delay to allow layout to stabilize
            setTimeout(() => {
              element.scrollIntoView({ behavior: 'smooth', block: 'start' })
            }, 100)
          }
        }, 100)

        // Safety cleanup after 10 seconds (extended for slower connections)
        const safetyTimeout = setTimeout(() => {
          clearInterval(checkForElement)
        }, 10000)

        return () => {
          clearInterval(checkForElement)
          clearTimeout(safetyTimeout)
        }
      }
    }
  }, [isLoading])

  return (
    <main className="min-h-screen bg-background">
      <AnimatePresence mode="wait">
        {isLoading && <Preloader onComplete={() => setIsLoading(false)} />}
      </AnimatePresence>

      <AnimatePresence>
        {!isLoading && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.6, ease: "easeOut" }}
          >
            <Header />

            <div className="overflow-x-clip">
              <motion.div
                initial="hidden"
                animate="visible"
                variants={{
                  hidden: { opacity: 0, y: 20 },
                  visible: {
                    opacity: 1,
                    y: 0,
                    transition: {
                      duration: 0.8,
                      ease: [0.22, 1, 0.36, 1],
                      delay: 0.2
                    }
                  }
                }}
              >
                <Hero />
              </motion.div>
            </div>

            <StudioImagery />

            {/* Other sections fade in normally as you scroll */}
            <div className="overflow-x-clip">
              <ProblemSolution />
              <Features />
              <LivePreview />
              <Testimonials />
              <Pricing />
              <Contact />
              <Footer />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
      <ExitPopup />
    </main>
  )
}
