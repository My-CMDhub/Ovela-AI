import { account } from "@/lib/appwrite";

/**
 * Universally authenticates requests to the Next.js /api/dashboard proxy.
 * Resolves the 401 Unauthorized third-party cookie block issue by generating
 * a fresh Appwrite JWT and attaching it as an Authorization header.
 */
export async function fetchWithAuth(url: string, options: RequestInit = {}): Promise<Response> {
    try {
        const { jwt } = await account.createJWT();

        const headers = new Headers(options.headers || {});
        headers.set("Authorization", `Bearer ${jwt}`);

        // Ensure Content-Type is json for POSTs unless specified otherwise
        if (!headers.has("Content-Type") && options.method && options.method !== "GET" && options.method !== "HEAD") {
            headers.set("Content-Type", "application/json");
        }

        return await fetch(url, {
            ...options,
            headers,
        });
    } catch (error) {
        console.error("Failed to generate JWT for API request:", error);
        throw new Error("Authentication failed");
    }
}
