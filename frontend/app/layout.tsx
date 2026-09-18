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
  preload: true,
})

export const metadata: Metadata = {
  title: {
    default: "Ovela | A voice AI receptionist, built and measured in production",
    template: "%s | Ovela"
  },
  description: "A voice AI receptionist that answers a real phone line, checks availability and handles bookings — built, measured and run in production as a personal engineering project.",
  keywords: [
    "AI receptionist for hotels",
    "hotel ai receptionist",
    "missed hotel calls",
    "hotel phone answering service",
    "24/7 hotel reception service",
    "hotel call center solution",
    "hotel answering service australia",
    "hotel answering service melbourne",
    "automated phone answering service Australia",
    "virtual receptionist Australia",
    "AI receptionist for small business",
    "missed call answering service Australia",
    "AI receptionist for tradies",
    "after hours answering service Australia",
    "phone answering service hospitality Australia",
    "AI phone answering 24 7",
    "automated booking service Australia",

  ],
  authors: [{ name: "Dhruv Patel" }],
  creator: "Dhruv Patel",
  openGraph: {
    type: "website",
    locale: "en_AU",
    url: "https://ovela.dev",
    title: "Ovela | A voice AI receptionist, built and measured in production",
    description: "A voice AI receptionist that answers a real phone line, checks availability and handles bookings — built, measured and run in production as a personal engineering project.",
    siteName: "Ovela",
    images: [
      {
        url: "/og-image.jpg",
        width: 1200,
        height: 630,
        alt: "Ovela — a voice AI receptionist"
      }
    ]
  },
  twitter: {
    card: "summary_large_image",
    title: "Ovela | A voice AI receptionist, built and measured in production",
    description: "A voice AI receptionist that answers a real phone line, checks availability and handles bookings — built, measured and run in production as a personal engineering project.",
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
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{
            __html: JSON.stringify({
              "@context": "https://schema.org",
              "@type": "SoftwareSourceCode",
              "name": "Ovela",
              "url": "https://ovela.dev",
              "codeRepository": "https://github.com/My-CMDhub/Ovela-AI",
              "programmingLanguage": ["Python", "TypeScript"],
              "description": "A voice AI receptionist built and run in production as a personal engineering project. Not a registered business; no customers.",
              "author": { "@type": "Person", "name": "Dhruv Patel" }
            })
          }}
        />
      </head>
      <body className={`font-sans antialiased ${dmSans.variable} ${playfair.variable} overflow-x-hidden`}>
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
