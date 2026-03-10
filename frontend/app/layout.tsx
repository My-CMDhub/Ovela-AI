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
    default: "Ovela | AI Phone Answering for Australian Service Businesses",
    template: "%s | Ovela"
  },
  description: "Ovela answers your calls, checks live availability, and books directly into your software — 24/7. No missed bookings, no interruptions. Australian AI receptionist. Free 21-day trial.",
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
    "ServiceM8 AI integration",
    "Cliniko phone answering automation",
    "phone answering service hospitality Australia",
    "AI phone answering 24 7",
    "automated booking service Australia",

  ],
  authors: [{ name: "Ovela AI" }],
  creator: "Ovela AI",
  openGraph: {
    type: "website",
    locale: "en_AU",
    url: "https://ovela.dev",
    title: "Ovela | AI Phone Answering for Australian Service Businesses",
    description: "Ovela answers your calls, checks live availability, and books directly into your software — 24/7. No missed bookings. Free 21-day trial.",
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
    title: "Ovela | AI Phone Answering for Australian Service Businesses",
    description: "Ovela answers your calls, checks live availability, and books directly into your software — 24/7. No missed bookings. Free 21-day trial.",
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
              "@graph": [
                {
                  "@type": "SoftwareApplication",
                  "name": "Ovela",
                  "url": "https://ovela.dev",
                  "description": "AI voice receptionist for Australian service businesses. Answers calls, checks live availability, and books directly into your existing software — 24/7.",
                  "applicationCategory": "BusinessApplication",
                  "operatingSystem": "Web",
                  "offers": {
                    "@type": "Offer",
                    "price": "200",
                    "priceCurrency": "AUD",
                    "availability": "https://schema.org/InStock"
                  },
                  "provider": {
                    "@type": "Organization",
                    "name": "Ovela",
                    "url": "https://ovela.dev",
                    "areaServed": "AU"
                  },
                  "featureList": [
                    "Answers calls 24/7",
                    "Books appointments directly in your software",
                    "Integrates with ServiceM8, Tradify, Cliniko, RMS Cloud and more",
                    "Handles reschedules and cancellations",
                    "Transfers urgent calls to staff"
                  ]
                },
                {
                  "@type": "Organization",
                  "name": "Ovela",
                  "url": "https://ovela.dev",
                  "description": "AI voice receptionist software for Australian service businesses",
                  "areaServed": "AU"
                }
              ]
            })
          }}
        />
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
