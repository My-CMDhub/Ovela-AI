"use client"

import { useEffect, Suspense } from 'react'
import { usePathname, useSearchParams } from 'next/navigation'
import Script from 'next/script'

// Extend Window interface for Facebook Pixel
declare global {
    interface Window {
        fbq?: any
        _fbq?: any
    }
}

function FacebookPixelInner() {
    const pathname = usePathname()
    const searchParams = useSearchParams()

    useEffect(() => {
        // Track page views on route change
        if (typeof window !== 'undefined' && window.fbq) {
            window.fbq('track', 'PageView')
        }
    }, [pathname, searchParams])

    return null
}

export default function FacebookPixel() {
    return (
        <>
            <Script
                id="facebook-pixel"
                strategy="lazyOnload"
                dangerouslySetInnerHTML={{
                    __html: `
            !function(f,b,e,v,n,t,s)
            {if(f.fbq)return;n=f.fbq=function(){n.callMethod?
            n.callMethod.apply(n,arguments):n.queue.push(arguments)};
            if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';
            n.queue=[];t=b.createElement(e);t.async=!0;
            t.src=v;s=b.getElementsByTagName(e)[0];
            s.parentNode.insertBefore(t,s)}(window, document,'script',
            'https://connect.facebook.net/en_US/fbevents.js');
            fbq('init', '${process.env.NEXT_PUBLIC_FACEBOOK_PIXEL_ID}');
            fbq('track', 'PageView');
          `,
                }}
            />
            <Suspense fallback={null}>
                <FacebookPixelInner />
            </Suspense>
            <noscript>
                <img
                    height="1"
                    width="1"
                    style={{ display: 'none' }}
                    src={`https://www.facebook.com/tr?id=${process.env.NEXT_PUBLIC_FACEBOOK_PIXEL_ID}&ev=PageView&noscript=1`}
                    alt=""
                />
            </noscript>
        </>
    )
}
