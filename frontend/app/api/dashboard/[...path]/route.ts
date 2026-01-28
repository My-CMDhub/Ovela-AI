import { NextRequest, NextResponse } from "next/server";

/**
 * Server-Side API Proxy for Dashboard
 * 
 * Proxies requests to the Python Backend.
 * CRITICAL: Rewrites /api/dashboard to /api/motel to ensure compatibility with
 * both Legacy/Production backends (which use /api/motel) and New/Local backends.
 */

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const API_KEY = process.env.DASHBOARD_API_KEY || "";

async function proxyRequest(request: NextRequest, path: string) {
    const url = new URL(request.url);

    // REWRITE STRATEGY:
    // The frontend always talks to /api/dashboard.
    // The backend (especially in production) might still be expecting /api/motel.
    // We rewrite here to ensure maximum compatibility.
    // /api/dashboard/settings -> /api/motel/settings
    // /api/dashboard/call-logs -> /api/motel/call-logs
    let backendPath = path;

    // We construct the target URL by swapping 'dashboard' for 'motel' effectively
    // But since 'path' here is the *suffix* (e.g. 'settings'), we just append it to /api/motel
    const targetUrl = `${BACKEND_URL}/api/motel/${path}${url.search}`;

    try {
        console.log(`[API Proxy] Rewrite: /api/dashboard/${path} -> ${targetUrl}`);

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

        const contentType = response.headers.get("content-type");
        if (contentType && contentType.includes("application/json")) {
            const data = await response.json();
            return NextResponse.json(data, { status: response.status });
        }

        const text = await response.text();
        console.error(`[API Proxy] Backend returned non-JSON (${response.status}):`, text.substring(0, 200));

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

export async function GET(
    request: NextRequest,
    { params }: { params: Promise<{ path: string[] }> }
) {
    const { path } = await params;
    const pathString = path.join("/");
    return proxyRequest(request, pathString);
}

export async function POST(
    request: NextRequest,
    { params }: { params: Promise<{ path: string[] }> }
) {
    const { path } = await params;
    const pathString = path.join("/");
    return proxyRequest(request, pathString);
}

export async function PATCH(
    request: NextRequest,
    { params }: { params: Promise<{ path: string[] }> }
) {
    const { path } = await params;
    const pathString = path.join("/");
    return proxyRequest(request, pathString);
}

export async function DELETE(
    request: NextRequest,
    { params }: { params: Promise<{ path: string[] }> }
) {
    const { path } = await params;
    const pathString = path.join("/");
    return proxyRequest(request, pathString);
}
