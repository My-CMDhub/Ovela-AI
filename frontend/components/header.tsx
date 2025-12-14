"use client"

import { useState, useEffect } from "react"
import { motion, useScroll, useTransform, AnimatePresence } from "framer-motion"
import Link from "next/link"
import { DarkModeToggle } from "./dark-mode-toggle"
import { Menu, X } from "lucide-react"

export function Header() {
  const [isDesktop, setIsDesktop] = useState(false)
  const [isSidebarOpen, setIsSidebarOpen] = useState(false)
  const { scrollY } = useScroll()

  // Transform scroll position to animation values
  const width = useTransform(scrollY, [0, 300], ["100%", "35%"])
  const y = useTransform(scrollY, [0, 300], [0, 12])
  const borderRadius = useTransform(scrollY, [0, 300], [0, 50])

  // Border colors: Bottom is always visible (or maybe fades out if we want a pure pill look? No, pill has border all around).
  // Top/Left/Right fade in.
  const borderColor = useTransform(
    scrollY,
    [0, 300],
    ["transparent", "color-mix(in srgb, var(--border), transparent 50%)"]
  )

  // We want border-bottom to be visible at start, and stay visible (as part of the pill).
  // So border-bottom color is constant (or matches the target color).
  const borderBottomColor = "color-mix(in srgb, var(--border), transparent 50%)"

  // Flash effect for top border when scrolling near the top
  const topFlash = useTransform(
    scrollY,
    [0, 5, 15],
    ["var(--accent)", "transparent", "transparent"]
  )

  useEffect(() => {
    const handleResize = () => {
      setIsDesktop(window.innerWidth >= 768)
    }

    handleResize()
    window.addEventListener("resize", handleResize)
    return () => window.removeEventListener("resize", handleResize)
  }, [])

  // Close sidebar when clicking outside or on a link
  const closeSidebar = () => setIsSidebarOpen(false)

  return (
    <>
      <motion.header
        style={{
          width: isDesktop ? width : "100%",
          y: isDesktop ? y : 0,
          borderRadius: isDesktop ? borderRadius : 0,
          borderTopColor: topFlash,
          borderLeftColor: isDesktop ? borderColor : "transparent",
          borderRightColor: isDesktop ? borderColor : "transparent",
          borderBottomColor: borderBottomColor,
        }}
        transition={{ duration: 12, ease: "easeInOut" }}
        className="fixed left-0 right-0 z-50 mx-auto bg-background/80 backdrop-blur-md shadow-sm border border-transparent" // border-transparent to set width/style but let style override colors
      >
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2">
            <span className="font-serif text-2xl tracking-tight">Ovela</span>
          </Link>

          <nav className="hidden md:flex items-center gap-8">
            <Link href="#features" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
              Features
            </Link>
            <Link href="#pricing" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
              Pricing
            </Link>
            <Link href="#contact" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
              Contact
            </Link>
          </nav>

          <div className="flex items-center gap-4">
            {/* Mobile Menu Button */}
            <button
              onClick={() => setIsSidebarOpen(!isSidebarOpen)}
              className="md:hidden p-2 hover:bg-muted/50 rounded-lg transition-colors"
              aria-label="Toggle menu"
            >
              <Menu className="h-5 w-5" />
            </button>

            {/* Desktop Dark Mode Toggle */}
            <div className="hidden md:block">
              <DarkModeToggle />
            </div>

            <Link
              href="#contact"
              className="px-5 py-2.5 bg-primary text-primary-foreground text-sm rounded-full hover:opacity-90 transition-opacity"
            >
              Get Started
            </Link>
          </div>
        </div>
      </motion.header>

      {/* Mobile Sidebar */}
      <AnimatePresence>
        {isSidebarOpen && (
          <>
            {/* Backdrop */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.3 }}
              onClick={closeSidebar}
              className="fixed inset-0 bg-black/50 backdrop-blur-sm z-[60] md:hidden"
            />

            {/* Sidebar */}
            <motion.div
              initial={{ x: "-100%" }}
              animate={{ x: 0 }}
              exit={{ x: "-100%" }}
              transition={{ type: "spring", damping: 30, stiffness: 300 }}
              className="fixed left-0 top-0 bottom-0 w-[280px] bg-background border-r border-border z-[70] md:hidden"
            >
              {/* Sidebar Header with Classic Branding Lines */}
              <div className="relative p-6 border-b border-border">
                {/* Decorative corner lines - classic premium branding */}
                <div className="absolute top-0 left-0 w-12 h-12 border-t-2 border-l-2 border-accent/30" />
                <div className="absolute bottom-0 right-0 w-12 h-12 border-b-2 border-r-2 border-accent/30" />

                <div className="flex items-center justify-between relative z-10">
                  <span className="font-serif text-2xl tracking-tight">Ovela</span>
                  <button
                    onClick={closeSidebar}
                    className="p-2 hover:bg-muted/50 rounded-lg transition-colors"
                    aria-label="Close menu"
                  >
                    <X className="h-5 w-5" />
                  </button>
                </div>

                {/* Subtle accent line */}
                <div className="absolute bottom-0 left-6 right-6 h-px bg-gradient-to-r from-transparent via-accent/50 to-transparent" />
              </div>

              {/* Navigation Links */}
              <nav className="p-6 space-y-1">
                <Link
                  href="#features"
                  onClick={closeSidebar}
                  className="block px-4 py-3 text-sm text-muted-foreground hover:text-foreground hover:bg-muted/50 rounded-lg transition-colors"
                >
                  Features
                </Link>
                <Link
                  href="#pricing"
                  onClick={closeSidebar}
                  className="block px-4 py-3 text-sm text-muted-foreground hover:text-foreground hover:bg-muted/50 rounded-lg transition-colors"
                >
                  Pricing
                </Link>
                <Link
                  href="#contact"
                  onClick={closeSidebar}
                  className="block px-4 py-3 text-sm text-muted-foreground hover:text-foreground hover:bg-muted/50 rounded-lg transition-colors"
                >
                  Contact
                </Link>
              </nav>

              {/* Theme Toggle at Bottom */}
              <div className="absolute bottom-0 left-0 right-0 p-6 border-t border-border">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">Theme</span>
                  <DarkModeToggle />
                </div>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  )
}
