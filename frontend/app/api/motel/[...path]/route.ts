import { NextRequest, NextResponse } from "next/server";

/**
 * Server-Side API Proxy for Motel Dashboard
 * 
 * This catch-all route proxies all motel API requests to the Python backend.
 * The Appwrite API key is handled SERVER-SIDE in Python, never exposed to browser.
 * 
 * Routes handled:
 * - /api/motel/stats → Backend /api/motel/stats
 * - /api/motel/reservations → Backend /api/motel/reservations
 * - /api/motel/guests → Backend /api/motel/guests
 */

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function proxyRequest(request: NextRequest, path: string) {
    const url = new URL(request.url);
    const targetUrl = `${BACKEND_URL}/api/motel/${path}${url.search}`;

    try {
        console.log(`[Motel API Proxy] Forwarding to: ${targetUrl}`);

        const response = await fetch(targetUrl, {
            method: request.method,
            headers: {
                "Content-Type": "application/json",
            },
            body: request.method !== "GET" && request.method !== "HEAD"
                ? await request.text()
                : undefined,
        });

        const contentType = response.headers.get("content-type");
        if (contentType && contentType.includes("application/json")) {
            const data = await response.json();
            return NextResponse.json(data, { status: response.status });
        }

        const text = await response.text();
        console.error(`[Motel API Proxy] Backend returned non-JSON (${response.status}):`, text.substring(0, 200));

        return new NextResponse(text, {
            status: response.status,
            headers: { "Content-Type": contentType || "text/plain" }
        });

    } catch (error) {
        console.error(`[Motel API Proxy] Request failed:`, error);
        return NextResponse.json(
            { success: false, error: "Failed to connect to backend" },
            { status: 502 }
        );
    }
}

// Handle GET requests
export async function GET(
    request: NextRequest,
    { params }: { params: Promise<{ path: string[] }> }
) {
    const { path } = await params;
    const pathString = path.join("/");
    return proxyRequest(request, pathString);
}

// Handle POST requests
export async function POST(
    request: NextRequest,
    { params }: { params: Promise<{ path: string[] }> }
) {
    const { path } = await params;
    const pathString = path.join("/");
    return proxyRequest(request, pathString);
}

// Handle PATCH requests
export async function PATCH(
    request: NextRequest,
    { params }: { params: Promise<{ path: string[] }> }
) {
    const { path } = await params;
    const pathString = path.join("/");
    return proxyRequest(request, pathString);
}

// Handle DELETE requests
export async function DELETE(
    request: NextRequest,
    { params }: { params: Promise<{ path: string[] }> }
) {
    const { path } = await params;
    const pathString = path.join("/");
    return proxyRequest(request, pathString);
}
