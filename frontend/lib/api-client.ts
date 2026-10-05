import { account } from "@/lib/appwrite";

/**
 * Universally authenticates requests to the Next.js /api/dashboard proxy.
 * Resolves the 401 Unauthorized third-party cookie block issue by generating
 * a fresh Appwrite JWT and attaching it as an Authorization header.
 * Guests (unauthenticated roles) will silently bypass JWT header generation
 * to allow public access to dashboard views.
 */
// Appwrite JWTs live 15 minutes, and account.createJWT() is rate-limited per
// user. Minting one per request (the notifications page polls every 30 s) used
// up that limit within the hour, after which requests silently went out
// without auth and every protected dashboard route answered 401. One token is
// reused for 10 minutes, and concurrent callers share a single mint.
const JWT_REUSE_MS = 10 * 60 * 1000;
let cachedJwt: { jwt: string; mintedAt: number } | null = null;
let pendingJwt: Promise<string | null> | null = null;

async function getJwt(forceFresh = false): Promise<string | null> {
    if (!forceFresh && cachedJwt && Date.now() - cachedJwt.mintedAt < JWT_REUSE_MS) {
        return cachedJwt.jwt;
    }
    if (!pendingJwt) {
        pendingJwt = (async () => {
            try {
                const { jwt } = await account.createJWT();
                cachedJwt = { jwt, mintedAt: Date.now() };
                return jwt;
            } catch (jwtError) {
                // Silently fall back to unauthenticated request (e.g. for guest judges)
                const errMessage = jwtError instanceof Error ? jwtError.message : String(jwtError);
                console.warn("Guest access / JWT generation skipped: requesting without auth header context.", errMessage);
                cachedJwt = null;
                return null;
            } finally {
                pendingJwt = null;
            }
        })();
    }
    return pendingJwt;
}

export async function fetchWithAuth(url: string, options: RequestInit = {}): Promise<Response> {
    try {
        const send = (jwt: string | null) => {
            const headers = new Headers(options.headers || {});
            if (jwt) {
                headers.set("Authorization", `Bearer ${jwt}`);
            }

            // Ensure Content-Type is json for POSTs unless specified otherwise
            if (!headers.has("Content-Type") && options.method && options.method !== "GET" && options.method !== "HEAD") {
                headers.set("Content-Type", "application/json");
            }

            return fetch(url, {
                ...options,
                headers,
            });
        };

        const jwt = await getJwt();
        const response = await send(jwt);
        // A cached token can be revoked early (logout elsewhere, session ended):
        // mint a fresh one and retry once rather than fail until the cache ages out.
        if (response.status === 401 && jwt) {
            cachedJwt = null;
            return await send(await getJwt(true));
        }
        return response;
    } catch (error) {
        const errMessage = error instanceof Error ? error.message : String(error);
        console.error("Failed to execute API request:", errMessage);
        throw new Error("API request failed");
    }
}
