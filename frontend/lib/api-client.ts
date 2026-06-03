import { account } from "@/lib/appwrite";

/**
 * Universally authenticates requests to the Next.js /api/dashboard proxy.
 * Resolves the 401 Unauthorized third-party cookie block issue by generating
 * a fresh Appwrite JWT and attaching it as an Authorization header.
 * Guests (unauthenticated roles) will silently bypass JWT header generation
 * to allow public access to dashboard views.
 */
export async function fetchWithAuth(url: string, options: RequestInit = {}): Promise<Response> {
    try {
        let jwt: string | null = null;
        try {
            const jwtResult = await account.createJWT();
            jwt = jwtResult.jwt;
        } catch (jwtError) {
            // Silently fall back to unauthenticated request (e.g. for guest judges)
            const errMessage = jwtError instanceof Error ? jwtError.message : String(jwtError);
            console.warn("Guest access / JWT generation skipped: requesting without auth header context.", errMessage);
        }

        const headers = new Headers(options.headers || {});
        if (jwt) {
            headers.set("Authorization", `Bearer ${jwt}`);
        }

        // Ensure Content-Type is json for POSTs unless specified otherwise
        if (!headers.has("Content-Type") && options.method && options.method !== "GET" && options.method !== "HEAD") {
            headers.set("Content-Type", "application/json");
        }

        return await fetch(url, {
            ...options,
            headers,
        });
    } catch (error) {
        const errMessage = error instanceof Error ? error.message : String(error);
        console.error("Failed to execute API request:", errMessage);
        throw new Error("API request failed");
    }
}
