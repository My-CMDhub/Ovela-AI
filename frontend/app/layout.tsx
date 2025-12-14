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
    default: "Ovela – AI Receptionist for Australian Businesses",
    template: "%s | Ovela"
  },
  description: "Never miss a booking. AI-powered WhatsApp and phone assistant that handles enquiries, bookings, and follow-ups 24/7 for service businesses across Australia.",
  keywords: [
    "AI receptionist Australia",
    "WhatsApp booking automation",
    "AI answering service",
    "salon booking software",
    "trades booking system",
    "healthcare appointment booking",
    "small business automation",
    "automated phone answering",
    "24/7 virtual receptionist"
  ],
  authors: [{ name: "Ovela AI" }],
  creator: "Ovela AI",
  openGraph: {
    type: "website",
    locale: "en_AU",
    url: "https://ovela.dev",
    title: "Ovela – AI Receptionist for Australian Businesses",
    description: "Never miss a booking. AI-powered WhatsApp and phone assistant for service businesses.",
    siteName: "Ovela",
    images: [
      {
        url: "/og-image.jpg",
        width: 1200,
        height: 630,
        alt: "Ovela AI - Never miss a booking"
      }
    ]
  },
  twitter: {
    card: "summary_large_image",
    title: "Ovela – AI Receptionist for Australian Businesses",
    description: "Never miss a booking. AI-powered WhatsApp and phone assistant.",
    images: ["/og-image.jpg"],
    creator: "@ovela_ai"
  },
  icons: {
    icon: [
      { url: '/favicon.ico', sizes: 'any' },
      { url: '/favicon-16x16.png', sizes: '16x16', type: 'image/png' },
      { url: '/favicon-32x32.png', sizes: '32x32', type: 'image/png' },
      { url: '/android-chrome-192x192.png', sizes: '192x192', type: 'image/png' },
      { url: '/android-chrome-512x512.png', sizes: '512x512', type: 'image/png' },
    ],
    apple: '/apple-touch-icon.png',
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
