import { NextRequest, NextResponse } from "next/server";

/**
 * Server-Side API Proxy for Dashboard
 * 
 * This catch-all route proxies all dashboard API requests to the Python backend.
 * The API key is added SERVER-SIDE, so it's never exposed to the browser.
 * 
 * Routes handled:
 * - /api/dashboard/stats → Backend /api/dashboard/stats
 * - /api/dashboard/bookings → Backend /api/dashboard/bookings
 * - /api/dashboard/bookings/today → Backend /api/dashboard/bookings/today
 * - /api/dashboard/settings → Backend /api/dashboard/settings
 * - /api/dashboard/requests → Backend /api/dashboard/requests
 * - /api/dashboard/requests/{id}/approve → Backend /api/dashboard/requests/{id}/approve
 * - /api/dashboard/requests/{id}/reject → Backend /api/dashboard/requests/{id}/reject
 * - etc.
 */

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const API_KEY = process.env.DASHBOARD_API_KEY || "";

async function proxyRequest(request: NextRequest, path: string) {
    const url = new URL(request.url);
    const targetUrl = `${BACKEND_URL}/api/dashboard/${path}${url.search}`;

    try {
        console.log(`[API Proxy] Forwarding to: ${targetUrl}`);

        const response = await fetch(targetUrl, {
            method: request.method,
            headers: {
                "Content-Type": "application/json",
                "X-API-Key": API_KEY,
            },
            body: request.method !== "GET" && request.method !== "HEAD"
                ? await request.text()
                : undefined,
        });

        // 1. Check if response is JSON
        const contentType = response.headers.get("content-type");
        if (contentType && contentType.includes("application/json")) {
            const data = await response.json();
            return NextResponse.json(data, { status: response.status });
        }

        // 2. Handle non-JSON response (likely an error page)
        const text = await response.text();
        console.error(`[API Proxy] Backend returned non-JSON (${response.status}):`, text.substring(0, 200)); // Log first 200 chars

        return new NextResponse(text, {
            status: response.status,
            headers: { "Content-Type": contentType || "text/plain" }
        });

    } catch (error) {
        console.error(`[API Proxy] Request failed:`, error);
        return NextResponse.json(
            { success: false, error: "Failed to connect to backend proxy" },
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
