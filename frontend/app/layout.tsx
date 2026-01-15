import type React from "react"
import type { Metadata } from "next"
import { DM_Sans, Playfair_Display } from "next/font/google"
import { Analytics } from "@vercel/analytics/next"
import { SpeedInsights } from "@vercel/speed-insights/next"
import GoogleAnalytics from "@/components/google-analytics"
import FacebookPixel from "@/components/facebook-pixel"
import "./globals.css"

const dmSans = DM_Sans({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
  preload: true,
})

const playfair = Playfair_Display({
  subsets: ["latin"],
  variable: "--font-serif",
  display: "swap",
  preload: false, // Decorative font, load after critical content
})

export const metadata: Metadata = {
  title: {
    default: "Ovela | Enterprise-Grade AI Phone Agents",
    template: "%s | Ovela"
  },
  description: "Empower your business with Ovela's human-like AI. Instantly handle 100% of phone calls, secure bookings, and drive revenue 24/7 without lifting a finger.",
  keywords: [
    "Enterprise AI Voice Agent",
    "Automated Receptionist Australia",
    "Business Phone Automation",
    "AI Phone Answering Service",
    "24/7 Booking Assistant",
    "Healthcare Appointment AI",
    "Trades Scheduling Automation",
    "Revenue Driving AI",
    "Human-like Voice AI"
  ],
  authors: [{ name: "Ovela AI" }],
  creator: "Ovela AI",
  openGraph: {
    type: "website",
    locale: "en_AU",
    url: "https://ovela.dev",
    title: "Ovela | Enterprise-Grade AI Phone Agents",
    description: "Empower your business with Ovela's human-like AI. Instantly handle 100% of phone calls, secure bookings, and drive revenue 24/7.",
    siteName: "Ovela",
    images: [
      {
        url: "/og-image.jpg",
        width: 1200,
        height: 630,
        alt: "Ovela AI - Enterprise-Grade Phone Automation"
      }
    ]
  },
  twitter: {
    card: "summary_large_image",
    title: "Ovela | Enterprise-Grade AI Phone Agents",
    description: "Empower your business with Ovela's human-like AI. Instantly handle 100% of phone calls, secure bookings, and drive revenue 24/7.",
    images: ["/og-image.jpg"],
    creator: "@ovela_ai"
  },
  icons: {
    icon: [
      { url: '/favicon.svg', type: 'image/svg+xml' },
      { url: '/favicon.ico', sizes: 'any' },
      { url: '/favicon-16x16.png', sizes: '16x16', type: 'image/png' },
      { url: '/favicon-32x32.png', sizes: '32x32', type: 'image/png' },
      { url: '/android-chrome-192x192.png', sizes: '192x192', type: 'image/png' },
      { url: '/android-chrome-512x512.png', sizes: '512x512', type: 'image/png' },
    ],
    apple: [
      { url: '/apple-touch-icon.png', sizes: '180x180', type: 'image/png' },
    ],
    other: [
      { rel: 'mask-icon', url: '/favicon.svg', color: '#000000' },
    ],
  },
}

export const viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 5,
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en">
      <head>
        {/* DNS Prefetch for external resources */}
        <link rel="dns-prefetch" href="https://images.unsplash.com" />
        <link rel="dns-prefetch" href="https://www.googletagmanager.com" />
        <link rel="dns-prefetch" href="https://connect.facebook.net" />
        <link rel="preconnect" href="https://images.unsplash.com" crossOrigin="anonymous" />
      </head>
      <body className={`font-sans antialiased ${dmSans.variable} ${playfair.variable}`}>
        {children}
        <Analytics />
        <SpeedInsights />
        {/* Load analytics after page is interactive */}
        <GoogleAnalytics />
        <FacebookPixel />
      </body>
    </html>
  )
}
