'use client'

import Script from 'next/script'

export default function GoogleAnalytics() {
    return (
        <>
            <Script
                strategy="lazyOnload"
                src={`https://www.googletagmanager.com/gtag/js?id=G-P3H1KQ1968`}
            />
            <Script
                id="google-analytics"
                strategy="lazyOnload"
                dangerouslySetInnerHTML={{
                    __html: `
            window.dataLayer = window.dataLayer || [];
            function gtag(){dataLayer.push(arguments);}
            gtag('js', new Date());
            gtag('config', 'G-P3H1KQ1968', {
              page_path: window.location.pathname,
            });
          `,
                }}
            />
        </>
    )
}
