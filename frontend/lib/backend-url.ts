/**
 * The backend every browser fetch and every Next.js proxy route talks to.
 *
 * NEXT_PUBLIC_API_URL is inlined at BUILD time. It was still set to the
 * retired Cloud Run service (ovela-backend-…a.run.app), which now answers 404
 * with no CORS headers, so the demo form on ovela.dev failed its preflight
 * ("No 'Access-Control-Allow-Origin' header") and every visitor saw an error.
 * The backend runs on Heroku; its CORS already allows ovela.dev.
 *
 * A value pointing at the retired host is ignored rather than trusted, so a
 * stale environment variable cannot take the form down again. Set
 * NEXT_PUBLIC_API_URL to the Heroku URL on the hosting platform anyway, and
 * rebuild: the variable is read at build time, not at request time.
 */
const DEFAULT_BACKEND_URL = "https://ovela-12c561a30285.herokuapp.com"
const RETIRED_HOSTS = /\.a\.run\.app$/i

function resolveBackendUrl(raw: string | undefined): string {
    const value = (raw || "").trim().replace(/\/+$/, "")
    if (!value) return DEFAULT_BACKEND_URL
    try {
        if (RETIRED_HOSTS.test(new URL(value).hostname)) return DEFAULT_BACKEND_URL
    } catch {
        return DEFAULT_BACKEND_URL
    }
    return value
}

export const BACKEND_URL = resolveBackendUrl(process.env.NEXT_PUBLIC_API_URL)
export { resolveBackendUrl }
