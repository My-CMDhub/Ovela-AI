"use client"

import { useState, useEffect } from "react"
import dynamic from "next/dynamic"
import { AnimatePresence, motion } from "framer-motion"
import { Header } from "@/components/header"
import { Hero } from "@/components/hero"
import { Preloader } from "@/components/preloader"
import { ExitPopup } from "@/components/ui/ExitPopup"
import { Footer } from "@/components/footer"

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

const FAQ = dynamic(() => import("@/components/faq").then(mod => ({ default: mod.FAQ })), {
  loading: () => <div className="min-h-[400px]" />,
  ssr: false,
})

const LogoLoop = dynamic(() => import("@/components/logo-loop").then(mod => ({ default: mod.LogoLoop })), {
  loading: () => <div className="h-20" />,
  ssr: false,
})

const partnerLogos = [
  { src: "/logo/servicem8-logo.png", alt: "ServiceM8", width: 150, height: 40, className: "!h-[60px]" },
  { src: "/logo/RMS logo .webp", alt: "RMS Cloud", width: 120, height: 40, className: "!h-[55px]" },
  { src: "/logo/Tradify-Logo.png", alt: "Tradify", width: 140, height: 40, className: "!h-[60px]" },
  { src: "/logo/cliniko-logo.png", alt: "Cliniko", width: 130, height: 40, className: "!h-[50px]" },
  { src: "/logo/Fergus-logo-black.png", srcDark: "/logo/Fergus-logo.png", alt: "Fergus", width: 140, height: 40, className: "!h-[75px] dark:!h-[100px]" },
  { src: "/logo/xero-logo.png", alt: "Xero", width: 100, height: 40, className: "!h-[65px]" },
  { src: "/logo/Halaxy-logo.png", alt: "Halaxy", width: 120, height: 40, className: "!h-[60px]" },
  { src: "/logo/apaleo-logo-dark.webp", srcDark: "/logo/apaleo-logo-white.png", alt: "Apaleo", width: 120, height: 40, className: "!h-[50px]" },
  { src: "/logo/zoho-logo.png", alt: "Zoho CRM", width: 150, height: 40, className: "!h-[55px]" },
  { src: "/logo/Vagaro-Logo.png", alt: "Vagaro", width: 130, height: 40, className: "!h-[50px]" },
  { src: "/logo/cloudbeds-logo.avif", alt: "CloudBeds", width: 130, height: 40, className: "!h-[70px] dark:brightness-0 dark:invert" }
]

export default function Home() {
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    if (!isLoading) {
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

            {/* Logo Loop - Social Proof */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 1, duration: 1 }}
              className="py-16 border-b border-white/5 bg-background/50 backdrop-blur-sm"
            >
              <div className="container mx-auto px-6 mb-10 text-center">
                <p className="text-sm font-medium text-muted-foreground">Reads and writes directly to the software you already use</p>
              </div>
              <LogoLoop
                logos={partnerLogos}
                speed={30}
                direction="left"
                logoHeight={50}
                gap={80}
                pauseOnHover={true}
                scaleOnHover={true}
                fadeOut={true}
                fadeOutColor="var(--background)"
                className="opacity-80 hover:opacity-100 transition-opacity duration-300"
              />
            </motion.div>

            <StudioImagery />

            {/* Other sections fade in normally as you scroll */}
            <div className="overflow-x-clip">
              <ProblemSolution />
              <Features />
              <LivePreview />
              <Testimonials />
              <FAQ />
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
